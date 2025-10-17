"use strict";
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// google-drive/syncs/all-files.ts
var all_files_exports = {};
__export(all_files_exports, {
  default: () => fetchAllFiles
});
module.exports = __toCommonJS(all_files_exports);
async function fetchAllFiles(nango) {
  const batchSize = 100;
  let batch = [];
  const query = `trashed = false and mimeType != 'application/vnd.google-apps.folder'`;
  const proxyConfiguration = {
    endpoint: "drive/v3/files",
    params: {
      fields: "files(id, name, mimeType, webViewLink, parents, modifiedTime, createdTime, size, owners), nextPageToken",
      pageSize: batchSize.toString(),
      q: query,
      corpora: "user",
      supportsAllDrives: "false"
    },
    paginate: {
      response_path: "files"
    },
    retries: 10
  };
  for await (const files of nango.paginate(proxyConfiguration)) {
    for (const file of files) {
      batch.push({
        id: file.id,
        name: file.name,
        mimeType: file.mimeType,
        webViewLink: file.webViewLink,
        parents: file.parents || [],
        modifiedTime: file.modifiedTime,
        createdTime: file.createdTime,
        size: file.size ? parseInt(file.size) : void 0,
        trashed: false
      });
      if (batch.length >= batchSize) {
        await nango.batchSave(batch, "DriveFile");
        batch = [];
      }
    }
  }
  if (batch.length > 0) {
    await nango.batchSave(batch, "DriveFile");
  }
}
