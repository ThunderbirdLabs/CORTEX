import type { NangoAction } from '../../models.js';

/**
 * Downloads a file from Google Drive and returns the raw bytes as base64.
 *
 * For Google Workspace files (Docs, Sheets, Slides), use fetch-google-doc or fetch-google-sheet instead.
 *
 * @param nango - An instance of NangoAction
 * @param input - Object containing fileId
 * @returns File content as base64-encoded string
 */
export default async function runAction(nango: NangoAction, input: { id: string }): Promise<string> {
    if (!input.id) {
        throw new nango.ActionError({
            message: 'Invalid input',
            details: 'File ID is required.'
        });
    }

    try {
        // Download file from Google Drive
        // https://developers.google.com/drive/api/v3/reference/files/get
        const response = await nango.get({
            endpoint: `/drive/v3/files/${input.id}`,
            params: {
                alt: 'media'  // Download file content (not metadata)
            },
            retries: 3,
            responseType: 'arraybuffer'  // Get raw bytes
        });

        // Convert to base64
        const buffer = Buffer.from(response.data);
        return buffer.toString('base64');

    } catch (error) {
        throw new nango.ActionError({
            message: 'Failed to download file from Google Drive',
            details: error instanceof Error ? error.message : String(error)
        });
    }
}
