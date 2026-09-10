export interface Response {
  protocol_version: 1;
  engine_version: string;
  scan_id: string;
  correlation_id: string;
  state: 'ready' | 'complete' | 'incomplete' | 'error';
  complete: boolean;
  truncated: boolean;
  findings: Record<string, unknown>[];
  errors: Record<string, unknown>[];
  capabilities?: { profiles: string[]; transport: string; [key: string]: unknown };
  summary?: Record<string, unknown>;
  [key: string]: unknown;
}
export class ScanError extends Error {
  readonly code: string;
  readonly response?: Response;
  constructor(code: string, response?: Response);
}
export class Client {
  constructor(command: readonly string[], options: {engineVersion: string; timeoutMs?: number; maxOutputBytes?: number});
  handshake(options?: {signal?: AbortSignal}): Promise<Response>;
  scan(options: {authorizedRoot: string; target: string; profile?: string; maxFindings?: number; correlationId?: string; logicalRoot?: string; signal?: AbortSignal}): Promise<Response>;
  close(): Promise<void>;
}
