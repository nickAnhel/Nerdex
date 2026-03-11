export const TAG_FORMAT_HINT = "Only lowercase Latin and Cyrillic letters, no spaces, digits, or special characters.";
export const TAG_VALIDATION_MESSAGE = TAG_FORMAT_HINT;

const TAG_PATTERN = /^[a-zа-яё]+$/;


export function normalizeTagValue(value) {
    return value.trim();
}

export function getTagValidationError(value) {
    const normalizedValue = normalizeTagValue(value);

    if (!normalizedValue) {
        return "";
    }

    if (normalizedValue !== normalizedValue.toLowerCase()) {
        return TAG_VALIDATION_MESSAGE;
    }

    if (normalizedValue.length > 64 || !TAG_PATTERN.test(normalizedValue)) {
        return TAG_VALIDATION_MESSAGE;
    }

    return "";
}

export function dedupeTags(tags) {
    const seenTags = new Set();

    return tags.filter((tag) => {
        if (!tag || seenTags.has(tag)) {
            return false;
        }

        seenTags.add(tag);
        return true;
    });
}

export function normalizeTagList(tags) {
    return dedupeTags(
        (tags || [])
            .map((tag) => (typeof tag === "string" ? tag : tag?.slug))
            .map(normalizeTagValue)
            .filter(Boolean)
    );
}

export function areTagListsEqual(firstTags, secondTags) {
    if (firstTags.length !== secondTags.length) {
        return false;
    }

    return firstTags.every((tag, index) => tag === secondTags[index]);
}
