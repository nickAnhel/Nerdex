import { fireEvent, render, screen } from "@testing-library/react";

import VideoPlayer from "./VideoPlayer";


function setMediaProperty(element, property, value) {
    Object.defineProperty(element, property, {
        configurable: true,
        value,
    });
}

beforeEach(() => {
    HTMLMediaElement.prototype.play = jest.fn().mockResolvedValue(undefined);
    HTMLMediaElement.prototype.pause = jest.fn();
});

afterEach(() => {
    jest.restoreAllMocks();
});

const singleSource = [{
    id: "original",
    label: "Original",
    src: "https://example.com/video-original.mp4",
    mimeType: "video/mp4",
}];

test("renders custom controls and toggles playback from keyboard", () => {
    render(
        <VideoPlayer
            title="Keyboard video player"
            sources={singleSource}
            skin="article"
        />
    );

    const player = screen.getByLabelText("Keyboard video player");
    fireEvent.keyDown(player, { key: "k" });

    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(1);
});

test("chapter controls seek to chapter start time", () => {
    render(
        <VideoPlayer
            title="Chapter video player"
            sources={singleSource}
            skin="page"
            chapters={[{ title: "Middle", startsAtSeconds: 25 }]}
        />
    );

    const video = document.querySelector("video");
    setMediaProperty(video, "duration", 100);
    fireEvent.loadedMetadata(video);

    fireEvent.click(screen.getAllByRole("button", { name: /middle/i })[1]);

    expect(video.currentTime).toBe(25);
});

test("fires progress checkpoints once per threshold", () => {
    const handleProgressCheckpoint = jest.fn();

    render(
        <VideoPlayer
            title="Checkpoint video player"
            sources={singleSource}
            checkpoints={[25]}
            onProgressCheckpoint={handleProgressCheckpoint}
        />
    );

    const video = document.querySelector("video");
    setMediaProperty(video, "duration", 100);
    fireEvent.loadedMetadata(video);

    video.currentTime = 20;
    fireEvent.timeUpdate(video);
    video.currentTime = 25;
    fireEvent.timeUpdate(video);
    video.currentTime = 40;
    fireEvent.timeUpdate(video);

    expect(handleProgressCheckpoint).toHaveBeenCalledTimes(1);
    expect(handleProgressCheckpoint).toHaveBeenCalledWith(expect.objectContaining({
        checkpointPercent: 25,
        currentTime: 25,
        duration: 100,
        qualityId: "original",
    }));
});

test("fires quality change event with previous and next quality ids", () => {
    const handleQualityChange = jest.fn();

    render(
        <VideoPlayer
            title="Quality video player"
            sources={[
                ...singleSource,
                {
                    id: "720p",
                    label: "720p",
                    src: "https://example.com/video-720p.mp4",
                    mimeType: "video/mp4",
                },
            ]}
            onQualityChange={handleQualityChange}
        />
    );

    const video = document.querySelector("video");
    setMediaProperty(video, "duration", 100);
    video.currentTime = 12;
    fireEvent.loadedMetadata(video);

    fireEvent.click(screen.getByRole("button", { name: /select video quality/i }));
    fireEvent.click(screen.getByRole("button", { name: "720p" }));
    fireEvent.loadedMetadata(video);

    expect(handleQualityChange).toHaveBeenCalledWith(expect.objectContaining({
        previousQualityId: "original",
        nextQualityId: "720p",
        qualityId: "720p",
        currentTime: 12,
    }));
});
