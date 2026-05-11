import { useEffect, useRef } from "react";

import { DEFAULT_CHECKPOINTS } from "./videoPlayerTypes";


function normalizeCheckpoints(checkpoints) {
    const source = Array.isArray(checkpoints) && checkpoints.length ? checkpoints : DEFAULT_CHECKPOINTS;
    return [...new Set(
        source
            .map((checkpoint) => Number(checkpoint))
            .filter((checkpoint) => Number.isFinite(checkpoint) && checkpoint > 0 && checkpoint <= 100)
    )].sort((a, b) => a - b);
}

export default function useProgressCheckpoints({
    currentTime,
    duration,
    checkpoints,
    selectedQualityId,
    playbackRate,
    volume,
    muted,
    onProgressCheckpoint,
}) {
    const firedCheckpointsRef = useRef(new Set());
    const normalizedCheckpoints = normalizeCheckpoints(checkpoints);

    useEffect(() => {
        firedCheckpointsRef.current = new Set();
    }, [selectedQualityId, duration]);

    useEffect(() => {
        if (!onProgressCheckpoint || !Number.isFinite(duration) || duration <= 0) {
            return;
        }

        const progressPercent = (currentTime / duration) * 100;
        const nextCheckpoint = normalizedCheckpoints.find((checkpoint) => (
            progressPercent >= checkpoint && !firedCheckpointsRef.current.has(checkpoint)
        ));

        if (!nextCheckpoint) {
            return;
        }

        firedCheckpointsRef.current.add(nextCheckpoint);
        onProgressCheckpoint({
            currentTime,
            duration,
            qualityId: selectedQualityId,
            playbackRate,
            volume,
            muted,
            checkpointPercent: nextCheckpoint,
        });
    }, [
        currentTime,
        duration,
        muted,
        normalizedCheckpoints,
        onProgressCheckpoint,
        playbackRate,
        selectedQualityId,
        volume,
    ]);
}
