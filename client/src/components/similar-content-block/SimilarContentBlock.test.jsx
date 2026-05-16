import { render, screen, waitFor } from "@testing-library/react";

jest.mock("../feed-content-card/FeedContentCard", () => ({ item }) => <div>Card {item.content_id}</div>);
jest.mock("../loader/Loader", () => () => <div>Loading</div>);
jest.mock("../../service/ContentService", () => ({
    __esModule: true,
    default: {
        getSimilarContent: jest.fn(),
    },
}));

import ContentService from "../../service/ContentService";
import SimilarContentBlock from "./SimilarContentBlock";


beforeEach(() => {
    jest.clearAllMocks();
});

test("renders similar content cards from API payload", async () => {
    ContentService.getSimilarContent.mockResolvedValue({
        data: {
            items: [
                { content: { content_id: "one", content_type: "post" } },
                { content: { content_id: "two", content_type: "video" } },
            ],
        },
    });

    render(<SimilarContentBlock contentId="content-1" />);

    await waitFor(() => expect(ContentService.getSimilarContent).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText("Card one")).not.toBeNull());
    expect(screen.getByText("Card two")).not.toBeNull();
});

test("renders empty state when API returns no items", async () => {
    ContentService.getSimilarContent.mockResolvedValue({
        data: {
            items: [],
        },
    });

    render(<SimilarContentBlock contentId="content-1" />);

    await waitFor(() => expect(screen.getByText("Похожих публикаций пока нет.")).not.toBeNull());
});

test("hides block on fetch error by default", async () => {
    const consoleSpy = jest.spyOn(console, "log").mockImplementation(() => {});
    ContentService.getSimilarContent.mockRejectedValue(new Error("failed"));

    render(<SimilarContentBlock contentId="content-1" />);

    await waitFor(() => expect(ContentService.getSimilarContent).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByRole("heading", { name: "Похожие публикации" })).toBeNull());
    consoleSpy.mockRestore();
});

test("shows error state when hideOnError is disabled", async () => {
    const consoleSpy = jest.spyOn(console, "log").mockImplementation(() => {});
    ContentService.getSimilarContent.mockRejectedValue(new Error("failed"));

    render(<SimilarContentBlock contentId="content-1" hideOnError={false} />);

    await waitFor(() => expect(screen.getByText("Не удалось загрузить похожие публикации.")).not.toBeNull());
    consoleSpy.mockRestore();
});
