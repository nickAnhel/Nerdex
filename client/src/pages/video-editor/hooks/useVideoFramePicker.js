import { useRef, useState } from "react";


export default function useVideoFramePicker({ onCoverCaptured }) {
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const [metadata, setMetadata] = useState(null);
    const [frameSecond, setFrameSecond] = useState(0);

    const loadMetadataFromVideo = () => {
        const node = videoRef.current;
        if (!node) {
            return;
        }
        const nextMetadata = {
            duration: node.duration || 0,
            width: node.videoWidth || 0,
            height: node.videoHeight || 0,
            orientation: node.videoWidth === node.videoHeight
                ? "square"
                : node.videoWidth > node.videoHeight ? "landscape" : "portrait",
        };
        setMetadata(nextMetadata);
        setFrameSecond(Math.min(1, nextMetadata.duration || 0));
    };

    const setFrame = (nextSecond) => {
        const safeSecond = Math.max(0, Number(nextSecond) || 0);
        setFrameSecond(safeSecond);
        if (videoRef.current) {
            videoRef.current.currentTime = safeSecond;
        }
    };

    const captureCover = async () => {
        const videoNode = videoRef.current;
        const canvasNode = canvasRef.current;
        if (!videoNode || !canvasNode) {
            return;
        }
        canvasNode.width = videoNode.videoWidth || 1280;
        canvasNode.height = videoNode.videoHeight || 720;
        const context = canvasNode.getContext("2d");
        context.drawImage(videoNode, 0, 0, canvasNode.width, canvasNode.height);
        const blob = await new Promise((resolve) => canvasNode.toBlob(resolve, "image/webp", 0.92));
        if (!blob) {
            throw new Error("Failed to capture cover frame.");
        }
        const file = new File([blob], "video-cover.webp", { type: "image/webp" });
        await onCoverCaptured(file, URL.createObjectURL(blob));
    };

    return {
        videoRef,
        canvasRef,
        metadata,
        setMetadata,
        frameSecond,
        loadMetadataFromVideo,
        setFrame,
        captureCover,
    };
}
