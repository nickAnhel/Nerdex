import { useMemo, useState } from "react";

import { normalizeTagList } from "../../../utils/tags";


const DEFAULT_FORM = {
    title: "",
    description: "",
    visibility: "private",
    status: "draft",
    publishRequestedAt: null,
    tags: [],
    chapters: [],
};

export default function useVideoEditorForm() {
    const [form, setForm] = useState(DEFAULT_FORM);
    const [tagInputState, setTagInputState] = useState({ error: "" });

    const loadVideo = (video) => {
        setForm({
            title: video.title || "",
            description: video.description || "",
            visibility: video.visibility || "private",
            status: video.status || "draft",
            publishRequestedAt: video.publish_requested_at || null,
            tags: normalizeTagList(video.tags),
            chapters: video.chapters || [],
        });
    };

    const updateField = (field, value) => {
        setForm((prevForm) => ({ ...prevForm, [field]: value }));
    };

    const setChapters = (chapters) => {
        setForm((prevForm) => ({ ...prevForm, chapters }));
    };

    const buildPayload = ({ sourceAsset, coverAsset, publish = false }) => ({
        source_asset_id: sourceAsset.asset_id,
        cover_asset_id: coverAsset.asset_id,
        title: form.title,
        description: form.description,
        visibility: form.visibility,
        status: publish ? "published" : form.status,
        tags: form.tags,
        chapters: form.chapters.map((chapter) => ({
            title: chapter.title,
            startsAtSeconds: Number(chapter.startsAtSeconds),
        })),
    });

    const validationError = useMemo(() => {
        if (tagInputState.error) {
            return tagInputState.error;
        }
        return "";
    }, [tagInputState.error]);

    return {
        form,
        setForm,
        loadVideo,
        updateField,
        setChapters,
        buildPayload,
        tagInputState,
        setTagInputState,
        validationError,
    };
}
