import * as z from 'zod';

// Attachment schema
export const Attachments = z.object({
    filename: z.string(),
    mimeType: z.string(),
    size: z.number(),
    attachmentId: z.string()
});

// Gmail Email schema - all fields must be present for Nango
export const GmailEmail = z.object({
    id: z.string(),
    sender: z.string(),
    recipients: z.string(),
    date: z.string(),
    subject: z.string(),
    body: z.string(),
    attachments: z.array(Attachments),
    threadId: z.string()
});

// Optional backfill setting for metadata
export const OptionalBackfillSetting = z.object({
    backfillPeriodMs: z.number()
});

export type Attachments = z.infer<typeof Attachments>;
export type GmailEmail = z.infer<typeof GmailEmail>;
export type OptionalBackfillSetting = z.infer<typeof OptionalBackfillSetting>;
