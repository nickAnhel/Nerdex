import { useMemo } from "react";


function parseChapterTime(value) {
    const text = String(value || "").trim();
    if (!text) {
        return { valid: false, seconds: 0, error: "time is required" };
    }
    if (!/^\d+(?::\d{1,2}){0,2}$/.test(text)) {
        return { valid: false, seconds: 0, error: "use seconds, mm:ss, or hh:mm:ss" };
    }
    const parts = text.split(":").map((part) => Number(part));
    if (parts.some((part) => !Number.isInteger(part) || part < 0)) {
        return { valid: false, seconds: 0, error: "time must be non-negative" };
    }
    if (parts.length > 1 && parts.slice(1).some((part) => part > 59)) {
        return { valid: false, seconds: 0, error: "minutes and seconds must be below 60" };
    }
    const seconds = parts.reduce((total, part) => total * 60 + part, 0);
    return { valid: true, seconds, error: "" };
}

export default function useVideoChapters({ chapters, setChapters, durationSeconds }) {
    const sortedChapters = useMemo(() => (
        [...(chapters || [])].sort((a, b) => Number(a.startsAtSeconds) - Number(b.startsAtSeconds))
    ), [chapters]);

    const addChapterAt = (startsAtSeconds = 0) => {
        setChapters([
            ...(chapters || []),
            { title: "", startsAtSeconds: Math.max(0, Math.floor(Number(startsAtSeconds) || 0)) },
        ]);
    };

    const updateChapter = (index, patch) => {
        const target = sortedChapters[index];
        setChapters((chapters || []).map((chapter) => (
            chapter === target ? { ...chapter, ...patch } : chapter
        )));
    };

    const updateChapterTime = (index, value) => {
        const parsed = parseChapterTime(value);
        updateChapter(index, {
            timeInput: value,
            ...(parsed.valid ? { startsAtSeconds: parsed.seconds } : {}),
        });
    };

    const removeChapter = (index) => {
        const target = sortedChapters[index];
        setChapters((chapters || []).filter((chapter) => chapter !== target));
    };

    const validationErrors = sortedChapters.flatMap((chapter, index) => {
        const errors = [];
        const parsedTime = chapter.timeInput != null
            ? parseChapterTime(chapter.timeInput)
            : { valid: true, seconds: Number(chapter.startsAtSeconds), error: "" };
        const time = parsedTime.valid ? Number(parsedTime.seconds) : Number.NaN;
        if (!chapter.title?.trim()) {
            errors.push(`Chapter ${index + 1} needs a title.`);
        }
        if (!parsedTime.valid || !Number.isFinite(time) || time < 0) {
            errors.push(`Chapter ${index + 1} needs a valid time (${parsedTime.error || "non-negative time"}).`);
        }
        if (durationSeconds && time > durationSeconds) {
            errors.push(`Chapter ${index + 1} cannot start after the video duration.`);
        }
        return errors;
    });

    return {
        chapters: sortedChapters,
        addChapterAt,
        updateChapter,
        updateChapterTime,
        removeChapter,
        validationErrors,
    };
}
