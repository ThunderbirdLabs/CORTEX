// Gmail API types
// Based on Google's Gmail API v1 schema

export interface Schema$MessagePartBody {
    attachmentId?: string;
    data?: string;
    size?: number;
}

export interface Schema$MessagePartHeader {
    name: string;
    value: string;
}

export interface Schema$MessagePart {
    partId?: string;
    mimeType?: string;
    filename?: string;
    headers?: Schema$MessagePartHeader[];
    body?: Schema$MessagePartBody;
    parts?: Schema$MessagePart[];
}

export interface Schema$MessagePayload {
    partId?: string;
    mimeType?: string;
    filename?: string;
    headers?: Schema$MessagePartHeader[];
    body?: Schema$MessagePartBody;
    parts?: Schema$MessagePart[];
}

export interface Schema$Message {
    id?: string;
    threadId?: string;
    labelIds?: string[];
    snippet?: string;
    historyId?: string;
    internalDate?: string;
    payload?: Schema$MessagePayload;
    sizeEstimate?: number;
    raw?: string;
}
