export function formatVideoTime(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) {
        return "0:00";
    }

    const totalSeconds = Math.floor(seconds);
    const hours = Math.floor(totalSeconds / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const remainingSeconds = totalSeconds % 60;

    if (hours > 0) {
        return `${hours}:${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
    }

    return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

export function getRangeProgress(value, max) {
    const safeMax = Number.isFinite(max) && max > 0 ? max : 0;
    const safeValue = Number.isFinite(value) && value > 0 ? Math.min(value, safeMax || value) : 0;
    return safeMax > 0 ? (safeValue / safeMax) * 100 : 0;
}
