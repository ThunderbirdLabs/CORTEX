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

// google-drive/actions/fetch-document.ts
var fetch_document_exports = {};
__export(fetch_document_exports, {
  default: () => runAction
});
module.exports = __toCommonJS(fetch_document_exports);
async function runAction(nango, input) {
  if (!input.id) {
    throw new nango.ActionError({
      message: "Invalid input",
      details: "File ID is required."
    });
  }
  try {
    const response = await nango.get({
      endpoint: `/drive/v3/files/${input.id}`,
      params: {
        alt: "media"
        // Download file content (not metadata)
      },
      retries: 3,
      responseType: "arraybuffer"
      // Get raw bytes
    });
    const buffer = Buffer.from(response.data);
    return buffer.toString("base64");
  } catch (error) {
    throw new nango.ActionError({
      message: "Failed to download file from Google Drive",
      details: error instanceof Error ? error.message : String(error)
    });
  }
}
