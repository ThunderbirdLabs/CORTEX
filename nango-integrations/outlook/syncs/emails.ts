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

    const pageSize = 100;

    const config: ProxyConfiguration = {
        // https://learn.microsoft.com/en-us/graph/api/user-list-messages
        endpoint: '/v1.0/me/messages',
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
            limit: pageSize
        },
        retries: 10
    };

    for await (const messageList of nango.paginate<OutlookMessage>(config)) {
        const emails: OutlookEmail[] = [];

        for (const message of messageList) {
            let attachments: Attachment[] = [];

            if (message.hasAttachments) {
                attachments = await fetchAttachments(nango, message.id);
            }

            emails.push(mapEmail(message, attachments));
        }

        await nango.batchSave(emails, 'OutlookEmail');
        await nango.log(`Saved ${emails.length} Outlook emails`);
    }
}

async function fetchAttachments(nango: NangoSync, messageId: string): Promise<Attachment[]> {
    const config: ProxyConfiguration = {
        // https://learn.microsoft.com/en-us/graph/api/message-list-attachments
        endpoint: `/v1.0/me/messages/${messageId}/attachments`,
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

