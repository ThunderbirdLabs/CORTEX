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
    isInline?: boolean;
    contentId?: string;
    contentBytes?: string; // Base64-encoded attachment content
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
            isInline: boolean;
            contentId: string | null;
            contentBytes?: string; // Base64-encoded attachment content
            userId: string; // User ID for multi-mailbox attachment fetching
        }>;
    threadId: string;
    userId: string; // User ID for email owner
}

// Default to 1 week backfill (can be changed via metadata)
const DEFAULT_BACKFILL_MS = 14 * 24 * 60 * 60 * 1000; // 2 WEEKS

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
            $select: 'id,mail,displayName'
            // Note: Can't filter 'mail ne null' - Graph API doesn't support it, so we filter in code
        },
        retries: 10
    };

    const usersResponse = await nango.get<{ value: Array<{ id: string, mail: string, displayName: string }> }>(usersConfig);
    const allUsers = usersResponse.data.value || [];
    
    // Filter out users without email addresses
    const users = allUsers.filter((user: { id: string, mail: string, displayName: string }) => user.mail && user.mail.length > 0);

    await nango.log(`Found ${users.length} users with mailboxes (out of ${allUsers.length} total users)`);

    // For each user, sync their emails
    for (const user of users) {
        await nango.log(`Syncing emails for: ${user.displayName} (${user.mail})`);
        
        try {
            const config: ProxyConfiguration = {
                // Only fetch from main inbox folder (excludes Junk, Spam, Promotions, etc.)
                endpoint: `/v1.0/users/${user.id}/mailFolders/inbox/messages`,
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

                    // Log email details for debugging
                    const hasAttachmentsFlag = (message as any).hasAttachments;
                    const bodyHasCid = message.body?.content?.includes('[cid:') || message.body?.content?.includes('cid:');
                    await nango.log(`📧 Email: ${message.subject} | hasAttachments: ${hasAttachmentsFlag} | body has CID: ${bodyHasCid}`, { level: 'info' });

                    // Only fetch attachments if hasAttachments flag is true OR body has CID references
                    if (hasAttachmentsFlag || bodyHasCid) {
                        attachments = await fetchAttachmentsForUser(nango, user.id, message.id);
                    } else {
                        await nango.log(`   ⏭️  Skipping attachment fetch (no attachments)`, { level: 'info' });
                    }
                    
                    // Log if we found attachments for debugging
                    if (attachments.length > 0) {
                        await nango.log(`Found ${attachments.length} attachments for message: ${message.subject}`);
                    }

                    emails.push(mapEmail(message, attachments, user.id));
                }

                await nango.batchSave(emails, 'OutlookEmail');
                await nango.log(`Saved ${emails.length} emails for ${user.displayName}`);
            }
        } catch (error: any) {
            // Skip ALL errors for individual users - don't let one bad user break the entire sync
            const errorCode = error?.payload?.error?.code || error?.payload?.code || error?.error?.code || error?.code || 'Unknown';
            const errorMessage = error?.payload?.error?.message || error?.error?.message || error?.message || 'Unknown error';
            
            await nango.log(`⚠️ Skipping ${user.displayName} (${user.mail}): ${errorMessage} [${errorCode}]`, { level: 'warn' });
            // Continue to next user - don't fail the entire sync
            continue;
        }
    }
}

// No longer needed - attachment downloads happen on-demand via Nango action

// Update attachment function to work with specific user and get content per Nango docs
async function fetchAttachmentsForUser(nango: NangoSync, userId: string, messageId: string): Promise<Attachment[]> {
    const config: ProxyConfiguration = {
        endpoint: `/v1.0/users/${userId}/mailFolders/inbox/messages/${messageId}/attachments`,
        // Don't use $select - just get all attachment metadata
        retries: 10
    };

    await nango.log(`🔍 Checking attachments for message ${messageId} with endpoint: ${config.endpoint}`, { level: 'info' });

    try {
        const response = await nango.get<{ value: Attachment[] }>(config);
        const attachments = response.data.value || [];
        
        await nango.log(`📎 Graph API returned ${attachments.length} attachments for message ${messageId}`, { level: 'info' });
        
        if (attachments.length > 0) {
            await nango.log(`✅ Found attachments: ${attachments.map((a: Attachment) => `${a.name} (${a.contentType})`).join(', ')}`, { level: 'info' });
        }

        // Return attachment metadata only (no content download)
        // Backend will call Nango's /fetch-attachment action on-demand (like Google Drive)
        await nango.log(`   📎 Found ${attachments.length} attachments (metadata only, no download)`, { level: 'info' });
        
        return attachments.map((att: Attachment) => ({
            ...att,
            contentBytes: undefined // Backend downloads on-demand via Nango action
        }));
        
    } catch (error: any) {
        const errorCode = error?.payload?.error?.code || error?.payload?.code || error?.code || 'Unknown';
        const errorMessage = error?.payload?.error?.message || error?.error?.message || error?.message || 'Unknown error';
        
        await nango.log(`❌ Failed to fetch attachments for message ${messageId}: ${errorMessage} [${errorCode}]`, { level: 'error' });
        return [];
    }
}

function mapEmail(message: OutlookMessage, rawAttachments: Attachment[], userId: string): OutlookEmail {
    const sender = message.from?.emailAddress.address || '';
    const recipients = message.toRecipients?.map(r => r.emailAddress.address).join(', ') || '';
    const body = message.body?.content || '';
    
    const attachments = rawAttachments.map(att => ({
        attachmentId: att.id,
        mimeType: att.contentType,
        filename: att.name,
        size: att.size,
        isInline: att.isInline || false,
        contentId: att.contentId || null,
        userId: userId, // CRITICAL: Store userId for attachment fetching!
        ...(att.contentBytes ? { contentBytes: att.contentBytes } : {}) // Only include if defined
    }));

    return {
        id: message.id,
        sender,
        recipients,
        date: new Date(message.receivedDateTime).toISOString(),
        subject: message.subject || '(No Subject)',
        body,
        attachments,
        threadId: message.conversationId || message.id,
        userId: userId // Store userId at email level too
    };
}

