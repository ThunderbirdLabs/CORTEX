import type { NangoSync, ProxyConfiguration } from '../../models.js';

interface OutlookMessage {
    id: string;
    subject?: string;
    from?: {
        emailAddress: {
            name?: string;
            address: string;
        };
    };
    toRecipients?: Array<{
        emailAddress: {
            name?: string;
            address: string;
        };
    }>;
    receivedDateTime: string;
    body?: {
        contentType: string;
        content: string;
    };
    hasAttachments?: boolean;
    conversationId?: string;
    webLink?: string;
    changeKey?: string;
}

interface Attachment {
    id: string;
    contentType: string;
    name: string;
    size: number;
}

interface OutlookEmail {
    id: string;
    sender?: string;
    recipients?: string;
    date: string;
    subject: string;
    body: string;
    attachments: Array<{
        filename: string;
        mimeType: string;
        size: number;
        attachmentId: string;
    }>;
    threadId: string;
}

// Default to 1 week for testing (can be changed via metadata)
const DEFAULT_BACKFILL_MS = 7 * 24 * 60 * 60 * 1000; // 1 week

export default async function fetchData(nango: NangoSync) {
    const metadata = await nango.getMetadata<{ backfillPeriodMs?: number }>();
    const backfillMilliseconds = metadata?.backfillPeriodMs || DEFAULT_BACKFILL_MS;
    const backfillPeriod = new Date(Date.now() - backfillMilliseconds);
    const { lastSyncDate } = nango;
    const syncDate = lastSyncDate || backfillPeriod;

    // First, get all users in the organization
    const usersConfig: ProxyConfiguration = {
        endpoint: '/v1.0/users',
        params: {
            $select: 'id,mail,displayName',
            $filter: 'mail ne null'  // Only users with email addresses
        },
        retries: 10
    };

    const usersResponse = await nango.get<{ value: Array<{ id: string, mail: string, displayName: string }> }>(usersConfig);
    const users = usersResponse.data.value || [];

    await nango.log(`Found ${users.length} users to sync emails for`);

    // For each user, sync their emails
    for (const user of users) {
        await nango.log(`Syncing emails for: ${user.displayName} (${user.mail})`);
        
        const config: ProxyConfiguration = {
            // Change from /me/messages to /users/{userId}/messages
            endpoint: `/v1.0/users/${user.id}/messages`,
            params: {
                $filter: `receivedDateTime ge ${syncDate.toISOString()}`,
                $select: 'id,from,toRecipients,receivedDateTime,subject,hasAttachments,conversationId,body,webLink,changeKey'
            },
            headers: {
                Prefer: 'outlook.body-content-type="text"'
            },
            paginate: {
                type: 'link',
                limit_name_in_request: '$top',
                response_path: 'value',
                link_path_in_response_body: '@odata.nextLink',
                limit: 100
            },
            retries: 10
        };

        for await (const messageList of nango.paginate<OutlookMessage>(config)) {
            const emails: OutlookEmail[] = [];

            for (const message of messageList) {
                let attachments: Attachment[] = [];

                if (message.hasAttachments) {
                    attachments = await fetchAttachmentsForUser(nango, user.id, message.id);
                }

                emails.push(mapEmail(message, attachments));
            }

            await nango.batchSave(emails, 'OutlookEmail');
            await nango.log(`Saved ${emails.length} emails for ${user.displayName}`);
        }
    }
}

// Update attachment function to work with specific user
async function fetchAttachmentsForUser(nango: NangoSync, userId: string, messageId: string): Promise<Attachment[]> {
    const config: ProxyConfiguration = {
        endpoint: `/v1.0/users/${userId}/messages/${messageId}/attachments`,
        params: { $select: 'id,contentType,name,size' },
        retries: 10
    };

    try {
        const response = await nango.get<{ value: Attachment[] }>(config);
        return response.data.value || [];
    } catch (error) {
        await nango.log(`Failed to fetch attachments for message ${messageId}: ${error}`, { level: 'warn' });
        return [];
    }
}

function mapEmail(message: OutlookMessage, rawAttachments: Attachment[]): OutlookEmail {
    const sender = message.from?.emailAddress.address || '';
    const recipients = message.toRecipients?.map(r => r.emailAddress.address).join(', ') || '';
    const body = message.body?.content || '';
    
    const attachments = rawAttachments.map(att => ({
        attachmentId: att.id,
        mimeType: att.contentType,
        filename: att.name,
        size: att.size
    }));

    return {
        id: message.id,
        sender,
        recipients,
        date: new Date(message.receivedDateTime).toISOString(),
        subject: message.subject || '(No Subject)',
        body,
        attachments,
        threadId: message.conversationId || message.id
    };
}

