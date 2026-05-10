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
jest.mock("../moment-card/MomentCard", () => {
    const React = require("react");
    return React.forwardRef(({ moment }, ref) => (
        <div ref={ref}>Moment card: {moment.caption}</div>
    ));
});
jest.mock("../post-list-item/PostListItem", () => {
    const React = require("react");
    return React.forwardRef(() => <div>Post card</div>);
});

test("dispatches moment content to MomentCard", () => {
    render(
        <FeedContentCard
            item={{
                content_id: "moment-1",
                content_type: "moment",
                caption: "Feed moment",
            }}
        />
    );

    expect(screen.getByText("Moment card: Feed moment")).not.toBeNull();
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
