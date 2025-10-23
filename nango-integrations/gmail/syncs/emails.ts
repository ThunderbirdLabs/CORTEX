import type { NangoSync, ProxyConfiguration } from '../../models';

interface GmailMessage {
    id: string;
    threadId: string;
    labelIds: string[];
    snippet: string;
    historyId: string;
    internalDate: string;
    payload: {
        partId?: string;
        mimeType: string;
        filename?: string;
        headers: Array<{
            name: string;
            value: string;
        }>;
        body: {
            attachmentId?: string;
            size: number;
            data?: string;
        };
        parts?: Array<{
            partId: string;
            mimeType: string;
            filename?: string;
            headers: Array<{
                name: string;
                value: string;
            }>;
            body: {
                attachmentId?: string;
                size: number;
                data?: string;
            };
        }>;
    };
}

interface GmailAttachment {
    attachmentId: string;
    filename: string;
    mimeType: string;
    size: number;
    contentBytes?: string; // Base64 content
}

interface GmailEmail {
    id: string;
    sender: string;
    recipients: string;
    date: string;
    subject: string;
    body: string;
    attachments: GmailAttachment[];
    threadId: string;
}

const DEFAULT_BACKFILL_MS = 7 * 24 * 60 * 60 * 1000; // 1 week

export default async function fetchEmails(nango: NangoSync): Promise<void> {
    // Get sync metadata (lookback period)
    const metadata = await nango.getMetadata();
    const backfillPeriodMs = (metadata?.['backfillPeriodMs'] as number) || DEFAULT_BACKFILL_MS;
    
    // Calculate sync date (how far back to look)
    const syncDate = new Date(Date.now() - backfillPeriodMs);
    await nango.log(`🚀 Starting Gmail sync - looking back ${Math.round(backfillPeriodMs / (24 * 60 * 60 * 1000))} days from ${syncDate.toISOString()}`);

    // Gmail API query with date filter
    const query = `after:${Math.floor(syncDate.getTime() / 1000)}`;
    
    const config: ProxyConfiguration = {
        endpoint: '/gmail/v1/users/me/messages',
        params: {
            q: query,
            format: 'full' // Get full message details including body and attachments
        },
        paginate: {
            type: 'link',
            limit_name_in_request: 'maxResults',
            response_path: 'messages',
            link_path_in_response_body: 'nextPageToken',
            limit: 50 // Gmail's max is 500, but start smaller for debugging
        },
        retries: 10
    };

    await nango.log(`📬 Fetching Gmail messages with query: ${query}`);

    let emailCount = 0;
    let attachmentCount = 0;

    try {
        for await (const messageList of nango.paginate<GmailMessage>(config)) {
            const emails: GmailEmail[] = [];

            for (const message of messageList) {
                try {
                    // Parse email details
                    const headers = message.payload.headers || [];
                    const subject = headers.find(h => h.name.toLowerCase() === 'subject')?.value || 'No Subject';
                    const from = headers.find(h => h.name.toLowerCase() === 'from')?.value || '';
                    const to = headers.find(h => h.name.toLowerCase() === 'to')?.value || '';
                    const date = headers.find(h => h.name.toLowerCase() === 'date')?.value || new Date(parseInt(message.internalDate)).toISOString();

                    // Extract body content
                    let body = '';
                    if (message.payload.body?.data) {
                        body = Buffer.from(message.payload.body.data, 'base64').toString('utf-8');
                    } else if (message.payload.parts) {
                        // Multi-part message, find text/plain or text/html part
                        for (const part of message.payload.parts) {
                            if (part.mimeType === 'text/plain' || part.mimeType === 'text/html') {
                                if (part.body?.data) {
                                    body = Buffer.from(part.body.data, 'base64').toString('utf-8');
                                    break;
                                }
                            }
                        }
                    }

                    // Check for attachments and CID references
                    const hasAttachments = hasGmailAttachments(message);
                    const bodyHasCid = body.includes('[cid:') || body.includes('cid:');
                    await nango.log(`📧 Email: ${subject} | hasAttachments: ${hasAttachments} | body has CID: ${bodyHasCid}`, { level: 'info' });

                    // Fetch attachments
                    let attachments: GmailAttachment[] = [];
                    if (hasAttachments) {
                        attachments = await fetchGmailAttachments(nango, message);
                        if (attachments.length > 0) {
                            await nango.log(`Found ${attachments.length} attachments for message: ${subject}`);
                            attachmentCount += attachments.length;
                        }
                    }

                    // Map to unified format
                    const email: GmailEmail = {
                        id: message.id,
                        sender: from,
                        recipients: to,
                        date: date,
                        subject: subject,
                        body: body,
                        attachments: attachments,
                        threadId: message.threadId
                    };

                    emails.push(email);
                    emailCount++;

                } catch (error: any) {
                    await nango.log(`❌ Error processing message ${message.id}: ${error.message}`, { level: 'error' });
                }
            }

            // Save batch of emails
            if (emails.length > 0) {
                await nango.batchSave(emails, 'GmailEmail');
                await nango.log(`✅ Saved batch of ${emails.length} emails`);
            }
        }

        await nango.log(`🎉 Gmail sync completed! Processed ${emailCount} emails with ${attachmentCount} total attachments`);

    } catch (error: any) {
        await nango.log(`❌ Gmail sync failed: ${error.message}`, { level: 'error' });
        throw error;
    }
}

function hasGmailAttachments(message: GmailMessage): boolean {
    // Check main payload
    if (message.payload.body?.attachmentId) {
        return true;
    }
    
    // Check parts for attachments
    if (message.payload.parts) {
        for (const part of message.payload.parts) {
            if (part.body?.attachmentId && part.filename) {
                return true;
            }
        }
    }
    
    return false;
}

async function fetchGmailAttachments(nango: NangoSync, message: GmailMessage): Promise<GmailAttachment[]> {
    const attachments: GmailAttachment[] = [];
    
    await nango.log(`🔍 Checking attachments for Gmail message ${message.id}`, { level: 'info' });

    try {
        // Check main payload for attachment
        if (message.payload.body?.attachmentId && message.payload.filename) {
            const attachment = await downloadGmailAttachment(
                nango, 
                message.id, 
                message.payload.body.attachmentId,
                message.payload.filename,
                message.payload.mimeType,
                message.payload.body.size
            );
            if (attachment) {
                attachments.push(attachment);
            }
        }

        // Check parts for attachments
        if (message.payload.parts) {
            for (const part of message.payload.parts) {
                if (part.body?.attachmentId && part.filename) {
                    const attachment = await downloadGmailAttachment(
                        nango,
                        message.id,
                        part.body.attachmentId,
                        part.filename,
                        part.mimeType,
                        part.body.size
                    );
                    if (attachment) {
                        attachments.push(attachment);
                    }
                }
            }
        }

        await nango.log(`📎 Gmail API returned ${attachments.length} attachments for message ${message.id}`, { level: 'info' });
        
        if (attachments.length > 0) {
            await nango.log(`✅ Found attachments: ${attachments.map((a: GmailAttachment) => `${a.filename} (${a.mimeType})`).join(', ')}`, { level: 'info' });
        }

        return attachments;

    } catch (error: any) {
        const errorDetails = {
            message: error.message || 'Unknown error',
            status: error.response?.status || 'No status',
            statusText: error.response?.statusText || 'No status text',
            responseData: error.response?.data ? JSON.stringify(error.response.data).slice(0, 200) : 'No response data'
        };
        
        await nango.log(`❌ Failed to fetch attachments for Gmail message ${message.id}:`, { level: 'error' });
        await nango.log(`   Error: ${errorDetails.message}`, { level: 'error' });
        await nango.log(`   Status: ${errorDetails.status} ${errorDetails.statusText}`, { level: 'error' });
        await nango.log(`   Response: ${errorDetails.responseData}`, { level: 'error' });
        
        return [];
    }
}

async function downloadGmailAttachment(
    nango: NangoSync,
    messageId: string,
    attachmentId: string,
    filename: string,
    mimeType: string,
    size: number
): Promise<GmailAttachment | null> {
    
    // Skip if too large (>10MB)
    if (size > 10 * 1024 * 1024) {
        await nango.log(`   ⏭️  Skipping large attachment: ${filename} (${size} bytes)`, { level: 'info' });
        return {
            attachmentId,
            filename,
            mimeType,
            size
            // contentBytes omitted for large files
        };
    }

    // Skip unsupported types
    const supportedTypes = [
        'application/pdf',
        'text/plain',
        'text/csv',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp'
    ];
    
    if (!supportedTypes.includes(mimeType)) {
        await nango.log(`   ⏭️  Skipping unsupported attachment: ${filename} (${mimeType})`, { level: 'info' });
        return {
            attachmentId,
            filename,
            mimeType,
            size
            // contentBytes omitted for unsupported types
        };
    }

    try {
        await nango.log(`   📥 Downloading Gmail attachment: ${filename}`, { level: 'info' });

        const config: ProxyConfiguration = {
            endpoint: `/gmail/v1/users/me/messages/${messageId}/attachments/${attachmentId}`,
            retries: 5
        };

        const response = await nango.get(config);
        const data = response.data;

        if (data?.data) {
            // Gmail returns base64url-encoded data, convert to regular base64
            let contentBytes = data.data;
            contentBytes = contentBytes.replace(/-/g, '+').replace(/_/g, '/');
            
            // Add padding if needed
            const padding = contentBytes.length % 4;
            if (padding) {
                contentBytes += '='.repeat(4 - padding);
            }

            await nango.log(`   ✅ Downloaded ${filename} (${contentBytes.length} base64 chars)`, { level: 'info' });
            
            return {
                attachmentId,
                filename,
                mimeType,
                size,
                contentBytes
            };
        } else {
            await nango.log(`   ❌ No data returned for attachment: ${filename}`, { level: 'warn' });
            return null;
        }

    } catch (error: any) {
        await nango.log(`   ❌ Failed to download attachment ${filename}: ${error.message}`, { level: 'warn' });
        return {
            attachmentId,
            filename,
            mimeType,
            size
            // contentBytes omitted for failed downloads
        };
    }
}
