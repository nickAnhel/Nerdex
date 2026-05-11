import { useEffect } from "react";


function isEditableTarget(target) {
    const tagName = target?.tagName?.toLowerCase();
    return target?.isContentEditable || tagName === "input" || tagName === "textarea" || tagName === "select";
}

export default function useVideoKeyboardShortcuts(rootRef, commands) {
    useEffect(() => {
        const root = rootRef.current;
        if (!root) {
            return undefined;
        }

        const handleKeyDown = (event) => {
            if (isEditableTarget(event.target)) {
                return;
            }

            const key = event.key.toLowerCase();
            const handledKeys = [" ", "k", "arrowleft", "arrowright", "j", "l", "m", "f"];

            if (!handledKeys.includes(key)) {
                return;
            }

            event.preventDefault();

            if (key === " " || key === "k") {
                commands.togglePlay();
            } else if (key === "arrowleft") {
                commands.seekBy(-5);
            } else if (key === "arrowright") {
                commands.seekBy(5);
            } else if (key === "j") {
                commands.seekBy(-10);
            } else if (key === "l") {
                commands.seekBy(10);
            } else if (key === "m") {
                commands.toggleMute();
            } else if (key === "f") {
                commands.toggleFullscreen();
            }
        };

        root.addEventListener("keydown", handleKeyDown);
        return () => root.removeEventListener("keydown", handleKeyDown);
    }, [commands, rootRef]);
}
