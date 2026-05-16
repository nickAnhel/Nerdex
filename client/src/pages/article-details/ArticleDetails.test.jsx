import { fireEvent, render, screen, waitFor } from "@testing-library/react";

let mockStore = {
    isAuthenticated: true,
    refreshPosts: jest.fn(),
};

jest.mock("../..", () => ({
    StoreContext: require("react").createContext({
        get store() {
            return mockStore;
        },
    }),
}));
jest.mock("react-router-dom", () => ({
    Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
    useNavigate: () => jest.fn(),
    useParams: () => ({ articleId: "article-1" }),
}), { virtual: true });
jest.mock("../../components/loader/Loader", () => () => <div>Loading</div>);
jest.mock("../../components/modal/Modal", () => ({ children }) => <div>{children}</div>);
jest.mock("../../components/comment-section/CommentSection", () => () => <div />);
jest.mock("../../components/article-renderer/ArticleRenderer", () => () => <article>Article body</article>);
jest.mock("../../components/similar-content-block/SimilarContentBlock", () => () => <div />);
jest.mock("../../components/tag-chip/TagChip", () => ({ slug }) => <span>{slug}</span>);
jest.mock("../../components/icons/CommentIcon", () => () => <span />);
jest.mock("../../components/icons/DislikeIcon", () => () => <span />);
jest.mock("../../components/icons/LikeIcon", () => () => <span />);
jest.mock("../../components/icons/ArticleUiIcons", () => ({
    CopyIcon: () => <span />,
    EditIcon: () => <span />,
    ShareIcon: () => <span />,
    TrashIcon: () => <span />,
}));
jest.mock("../../service/ArticleService", () => ({
    __esModule: true,
    default: {
        getArticle: jest.fn(),
        deleteArticle: jest.fn(),
        likeArticle: jest.fn(),
        unlikeArticle: jest.fn(),
        dislikeArticle: jest.fn(),
        undislikeArticle: jest.fn(),
    },
}));
jest.mock("../../service/ContentService", () => ({
    __esModule: true,
    default: {
        startViewSession: jest.fn(),
        heartbeatViewSession: jest.fn(),
        finishViewSession: jest.fn(),
    },
}));

import ArticleService from "../../service/ArticleService";
import ContentService from "../../service/ContentService";
import ArticleDetails from "./ArticleDetails";


function article(overrides = {}) {
    return {
        article_id: "article-1",
        content_id: "article-1",
        title: "Tracked article",
        excerpt: "",
        body_markdown: "# Body",
        canonical_path: "/articles/article-1",
        reading_time_minutes: 3,
        word_count: 400,
        user: { username: "author", avatar: null },
        tags: [],
        toc: [],
        status: "published",
        visibility: "public",
        comments_count: 0,
        likes_count: 0,
        dislikes_count: 0,
        my_reaction: null,
        is_owner: false,
        created_at: "2026-05-04T00:00:00Z",
        updated_at: "2026-05-04T00:00:00Z",
        published_at: "2026-05-04T00:00:00Z",
        ...overrides,
    };
}

function setArticleScroll(progressPercent) {
    const page = document.getElementById("article-details");
    Object.defineProperty(page, "scrollHeight", { configurable: true, value: 1000 });
    Object.defineProperty(page, "clientHeight", { configurable: true, value: 500 });
    page.scrollTop = Math.floor((progressPercent / 100) * 500);
    fireEvent.scroll(page);
}

beforeEach(() => {
    jest.useFakeTimers();
    jest.clearAllMocks();
    mockStore = {
        isAuthenticated: true,
        refreshPosts: jest.fn(),
    };
    Object.defineProperty(document, "visibilityState", {
        configurable: true,
        value: "visible",
    });
    ArticleService.getArticle.mockResolvedValue({ data: article() });
    ContentService.startViewSession.mockResolvedValue({
        data: {
            view_session_id: "session-1",
            progress_percent: 0,
        },
    });
    ContentService.heartbeatViewSession.mockResolvedValue({
        data: {
            progress_percent: 30,
        },
    });
    ContentService.finishViewSession.mockResolvedValue({
        data: {
            progress_percent: 30,
        },
    });
});

afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
});

test("article detail starts a view session for authenticated users", async () => {
    render(<ArticleDetails />);

    await waitFor(() => expect(screen.getByText("Tracked article")).not.toBeNull());
    await waitFor(() => expect(ContentService.startViewSession).toHaveBeenCalledWith(
        "article-1",
        expect.objectContaining({
            source: "article_detail",
        }),
    ));
});

test("article heartbeat sends progress without position seconds", async () => {
    render(<ArticleDetails />);

    await waitFor(() => expect(screen.getByText("Tracked article")).not.toBeNull());
    setArticleScroll(30);
    jest.advanceTimersByTime(1600);

    await waitFor(() => expect(ContentService.heartbeatViewSession).toHaveBeenCalledWith(
        "article-1",
        "session-1",
        expect.objectContaining({
            progress_percent: 30,
            source: "article_detail",
        }),
    ));
    expect(ContentService.heartbeatViewSession.mock.calls[0][2]).not.toHaveProperty("position_seconds");
});

test("article tracking does not send parallel heartbeat requests", async () => {
    let resolveHeartbeat;
    ContentService.heartbeatViewSession.mockReturnValue(new Promise((resolve) => {
        resolveHeartbeat = resolve;
    }));

    render(<ArticleDetails />);

    await waitFor(() => expect(screen.getByText("Tracked article")).not.toBeNull());
    setArticleScroll(30);
    jest.advanceTimersByTime(1600);
    await waitFor(() => expect(ContentService.heartbeatViewSession).toHaveBeenCalledTimes(1));

    setArticleScroll(45);
    jest.advanceTimersByTime(1600);
    expect(ContentService.heartbeatViewSession).toHaveBeenCalledTimes(1);

    resolveHeartbeat({ data: { progress_percent: 45 } });
    await waitFor(() => expect(ContentService.heartbeatViewSession).toHaveBeenCalledTimes(2));
});

test("article read time does not accumulate while document is hidden", async () => {
    Object.defineProperty(document, "visibilityState", {
        configurable: true,
        value: "hidden",
    });

    render(<ArticleDetails />);

    await waitFor(() => expect(screen.getByText("Tracked article")).not.toBeNull());
    jest.advanceTimersByTime(11000);

    expect(ContentService.heartbeatViewSession).not.toHaveBeenCalled();
});
