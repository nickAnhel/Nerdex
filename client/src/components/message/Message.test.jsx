import { render, screen } from "@testing-library/react";

jest.mock("../..", () => {
    const React = require("react");
    return {
        StoreContext: React.createContext({
            store: {
                user: {
                    username: "alice",
                    avatar: null,
                },
            },
        }),
    };
});
jest.mock("react-router-dom", () => ({
    Link: ({ to, children, ...props }) => <a href={to} {...props}>{children}</a>,
}), { virtual: true });

import { StoreContext } from "../..";
import Message from "./Message";


test("renders aggregated emoji reactions without labels", () => {
    render(
        <StoreContext.Provider value={{ store: { user: { username: "alice", avatar: null } } }}>
            <Message
                messageId="message-1"
                username="You"
                content="Hello there"
                createdAt="2026-05-13T10:00:00Z"
                reactions={[
                    { reactionType: "like", count: 2, reactedByMe: true },
                    { reactionType: "heart", count: 1, reactedByMe: false },
                ]}
            />
        </StoreContext.Provider>
    );

    expect(screen.getByText("👍")).not.toBeNull();
    expect(screen.getByText("2")).not.toBeNull();
    expect(screen.getByText("❤️")).not.toBeNull();

    expect(screen.queryByText("Like")).toBeNull();
    expect(screen.queryByText("Heart")).toBeNull();
});
