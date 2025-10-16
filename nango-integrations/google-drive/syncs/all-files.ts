import type { NangoSync, DriveFile, ProxyConfiguration } from '../../models.js';

/**
 * Syncs ALL files from Google Drive (not just root folders).
 * Runs automatically every hour to detect new/updated files.
 * 
 * This sync fetches metadata only - use fetch-document action to download content.
 */
export default async function fetchAllFiles(nango: NangoSync): Promise<void> {
    const batchSize = 100;
    let batch: DriveFile[] = [];

    // Query to fetch all files (not trashed, not folders)
    const query = `trashed = false and mimeType != 'application/vnd.google-apps.folder'`;
    
    const proxyConfiguration: ProxyConfiguration = {
        endpoint: 'drive/v3/files',
        params: {
            fields: 'files(id, name, mimeType, webViewLink, parents, modifiedTime, createdTime, size, owners), nextPageToken',
            pageSize: batchSize.toString(),
            q: query,
            corpora: 'user',
            supportsAllDrives: 'false'
        },
        paginate: {
            response_path: 'files'
        },
        retries: 10
    };

    // Fetch and save all files
    for await (const files of nango.paginate<any>(proxyConfiguration)) {
        for (const file of files) {
            batch.push({
                id: file.id,
                name: file.name,
                mimeType: file.mimeType,
                webViewLink: file.webViewLink,
                parents: file.parents || [],
                modifiedTime: file.modifiedTime,
                createdTime: file.createdTime,
                size: file.size ? parseInt(file.size) : undefined,
                trashed: false
            });

            if (batch.length >= batchSize) {
                await nango.batchSave<DriveFile>(batch, 'DriveFile');
                batch = [];
            }
        }
    }

    // Save remaining files
    if (batch.length > 0) {
        await nango.batchSave<DriveFile>(batch, 'DriveFile');
    }
}

