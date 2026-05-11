export const PLAYBACK_SPEEDS = [0.5, 1, 1.25, 1.5, 2];
export const DEFAULT_CHECKPOINTS = [10, 25, 50, 75, 90];
export const DEFAULT_VOLUME = 0.85;

export const VIDEO_SKINS = {
    page: "page",
    article: "article",
    post: "post",
    chat: "chat",
    moments: "moments",
};

export function normalizeSources(sources = []) {
    return sources
        .filter((source) => source?.src)
        .map((source, index) => ({
            id: source.id || (index === 0 ? "original" : `source-${index + 1}`),
            label: source.label || source.id || (index === 0 ? "Original" : `Source ${index + 1}`),
            src: source.src,
            mimeType: source.mimeType || source.type || "",
            width: source.width,
            height: source.height,
            bitrate: source.bitrate,
            isOriginal: Boolean(source.isOriginal || source.id === "original" || index === 0),
        }));
}

export function normalizeChapters(chapters = []) {
    return chapters
        .filter((chapter) => chapter?.title && Number.isFinite(Number(chapter.startsAtSeconds)))
        .map((chapter, index) => ({
            id: chapter.id || `${index}-${chapter.startsAtSeconds}`,
            title: chapter.title,
            startsAtSeconds: Math.max(0, Number(chapter.startsAtSeconds)),
        }))
        .sort((a, b) => a.startsAtSeconds - b.startsAtSeconds);
}
