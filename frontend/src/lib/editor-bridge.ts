/**
 * What other parts of the app may ask of the open editor. The editor registers itself while mounted.
 * `flush` writes unsaved typing before the server rewrites the file (accepting a suggestion).
 */
export const editorBridge: {
  flush: () => Promise<void>;
  blockIndex: () => number;
} = {
  flush: async () => {},
  blockIndex: () => 0,
};
