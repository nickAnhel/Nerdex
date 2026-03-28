export function getAvatarUrl(user, size = "small") {
    if (size === "medium") {
        return user?.avatar?.medium_url || user?.avatar?.small_url || "/assets/profile.svg";
    }

    return user?.avatar?.small_url || user?.avatar?.medium_url || "/assets/profile.svg";
}

function formatCropPart(value) {
    if (typeof value !== "number" || Number.isNaN(value)) {
        return "0";
    }

    return value.toFixed(4);
}

export function getAvatarRenderKey(user, size = "small") {
    const crop = user?.avatar?.crop;
    const cropKey = crop
        ? [
            formatCropPart(crop.x),
            formatCropPart(crop.y),
            formatCropPart(crop.size),
        ].join(":")
        : "no-crop";

    return [
        size,
        user?.avatar_asset_id || "no-asset",
        cropKey,
        getAvatarUrl(user, size),
    ].join("|");
}
