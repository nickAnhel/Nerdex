import { render, screen } from "@testing-library/react";

jest.mock("../video-card/VideoCard", () => {
    const React = require("react");
    return React.forwardRef(({ video }, ref) => (
        <div ref={ref}>Video card: {video.title}</div>
    ));
});
jest.mock("../article-card/ArticleCard", () => {
    const React = require("react");
    return React.forwardRef(() => <div>Article card</div>);
});
jest.mock("../post-list-item/PostListItem", () => {
    const React = require("react");
    return React.forwardRef(() => <div>Post card</div>);
});

import FeedContentCard from "./FeedContentCard";


test("dispatches video content to VideoCard", () => {
    render(
        <FeedContentCard
            item={{
                content_id: "video-1",
                content_type: "video",
                title: "Feed video",
            }}
        />
    );

    expect(screen.getByText("Video card: Feed video")).not.toBeNull();
});
