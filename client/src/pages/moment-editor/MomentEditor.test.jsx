import { fireEvent, render, screen, waitFor } from "@testing-library/react";

let mockNavigate = jest.fn();
let mockParams = {};
let mockUploadFlow;
let mockFramePicker;

jest.mock("react-router-dom", () => ({
    Link: ({ to, children }) => <a href={to}>{children}</a>,
    useNavigate: () => mockNavigate,
    useParams: () => mockParams,
}), { virtual: true });

jest.mock("../..", () => ({
    StoreContext: require("react").createContext({
        store: {
            isAuthenticated: true,
        },
    }),
}));
jest.mock("../../components/loader/Loader", () => () => <div>Loading</div>);
jest.mock("../../components/unauthorized/Unauthorized", () => () => <div>Unauthorized</div>);
jest.mock("../../components/video-card/VideoCard", () => ({
    formatDuration: (value) => `${value}s`,
}));
jest.mock("../../components/tag-input/TagInput", () => (props) => (
    <div>
        <span>Tags</span>
        <button type="button" onClick={() => props.onChange(["react", "fastapi"])}>
            Add tags
        </button>
    </div>
));
jest.mock("../video-editor/components/VideoEditorComponents", () => ({
    VideoProcessingStatusPanel: () => <div>Status panel</div>,
    VideoSourcePicker: ({ children, metadata }) => (
        <section>
            <div>Video source</div>
            {metadata?.duration ? <span>{metadata.duration}</span> : null}
            {metadata?.width && metadata?.height ? <span>{metadata.width}x{metadata.height}</span> : null}
            {metadata?.orientation ? <span>{metadata.orientation}</span> : null}
            {children}
        </section>
    ),
    VideoFramePicker: ({ onUseSelectedFrame }) => (
        <button type="button" onClick={onUseSelectedFrame}>Use selected frame</button>
    ),
    VideoCoverPicker: () => <div>Cover image</div>,
}));
jest.mock("../video-editor/hooks/useVideoUploadFlow", () => ({
    __esModule: true,
    default: jest.fn(),
}));
jest.mock("../video-editor/hooks/useVideoFramePicker", () => ({
    __esModule: true,
    default: jest.fn(),
}));
jest.mock("../../service/MomentService", () => ({
    __esModule: true,
    default: {
        createMoment: jest.fn(),
        getMomentEditor: jest.fn(),
        updateMoment: jest.fn(),
    },
}));

import MomentService from "../../service/MomentService";
import useVideoFramePicker from "../video-editor/hooks/useVideoFramePicker";
import useVideoUploadFlow from "../video-editor/hooks/useVideoUploadFlow";
import MomentEditor from "./MomentEditor";


function readyAsset(overrides = {}) {
    return {
        asset_id: overrides.asset_id || "asset-1",
        status: "ready",
        original_filename: "moment.mp4",
        width: 720,
        height: 1280,
        duration_ms: 12000,
        variants: [],
        ...overrides,
    };
}

beforeEach(() => {
    jest.clearAllMocks();
    mockNavigate = jest.fn();
    mockParams = {};
    mockUploadFlow = {
        sourceAsset: readyAsset({ asset_id: "source-1" }),
        coverAsset: readyAsset({ asset_id: "cover-1", original_filename: "cover.webp" }),
        localVideoUrl: "blob:video",
        localCoverUrl: "blob:cover",
        selectedSourceFile: null,
        selectedCoverFile: null,
        assetUploadStates: { source: "ready", cover: "ready" },
        isUploading: false,
        uploadError: "",
        notice: "",
        canUseAssets: true,
        loadAssets: jest.fn(),
        handleVideoFile: jest.fn(),
        handleCoverFile: jest.fn(),
    };
    mockFramePicker = {
        videoRef: { current: null },
        canvasRef: { current: null },
        metadata: {
            duration: 12,
            width: 720,
            height: 1280,
            orientation: "portrait",
        },
        frameSecond: 1,
        loadMetadataFromVideo: jest.fn(),
        setMetadata: jest.fn(),
        setFrame: jest.fn(),
        captureCover: jest.fn(),
    };
    useVideoUploadFlow.mockImplementation(() => mockUploadFlow);
    useVideoFramePicker.mockImplementation(() => mockFramePicker);
    MomentService.createMoment.mockResolvedValue({
        data: {
            moment_id: "moment-1",
            content_id: "moment-1",
            status: "draft",
            visibility: "public",
            publish_requested_at: "2026-05-08T00:00:00Z",
            processing_status: "processing",
            source_asset: mockUploadFlow.sourceAsset,
            cover: mockUploadFlow.coverAsset,
        },
    });
});

test("publishes through the lightweight Moment composer and stores publish intent", async () => {
    render(<MomentEditor />);

    fireEvent.change(screen.getByLabelText(/caption/i), {
        target: { value: "Short product update" },
    });
    fireEvent.change(screen.getByLabelText(/visibility/i), {
        target: { value: "public" },
    });
    fireEvent.click(screen.getByText("Add tags"));
    fireEvent.click(screen.getByRole("button", { name: /^publish$/i }));

    await waitFor(() => expect(MomentService.createMoment).toHaveBeenCalledWith({
        source_asset_id: "source-1",
        cover_asset_id: "cover-1",
        caption: "Short product update",
        tags: ["react", "fastapi"],
        visibility: "public",
        status: "published",
    }));
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/moments/moment-1/edit", { replace: true }));
});

test("blocks non-portrait source before saving", () => {
    mockFramePicker.metadata = {
        duration: 12,
        width: 1280,
        height: 720,
        orientation: "landscape",
    };

    render(<MomentEditor />);

    expect(screen.getByText("Moments require portrait video.")).not.toBeNull();
    expect(screen.getByRole("button", { name: /^publish$/i }).disabled).toBe(true);
});
