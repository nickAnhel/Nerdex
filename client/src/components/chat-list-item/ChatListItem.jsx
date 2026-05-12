import { forwardRef, useContext } from "react";
import { NavLink } from "react-router-dom";

import "./ChatListItem.css"

import { StoreContext } from "../..";
import { getAvatarUrl } from "../../utils/avatar";

function formatChatTime(value) {
    if (!value) {
        return "";
    }

    const date = new Date(value);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();

    if (isToday) {
        return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }

    return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

function buildLastMessagePreview(lastMessage) {
    if (!lastMessage) {
        return {
            text: "No messages yet",
            isAttachmentOnly: false,
        };
    }

    const content = lastMessage.content || "";
    if (content.trim()) {
        return {
            text: content,
            isAttachmentOnly: false,
        };
    }

    const attachmentsCount = Array.isArray(lastMessage.attachments)
        ? lastMessage.attachments.length
        : 0;
    if (attachmentsCount > 0) {
        return {
            text: `${attachmentsCount} ${attachmentsCount === 1 ? "attachment" : "attachments"}`,
            isAttachmentOnly: true,
        };
    }

    return {
        text: "No messages yet",
        isAttachmentOnly: false,
    };
}


const ChatListItem = forwardRef((props, ref) => {
    const { store } = useContext(StoreContext);
    const chat = props.chat;
    const directMember = chat.chat_type === "direct"
        ? chat.members?.find((member) => member.user_id !== store.user.user_id)
        : null;
    const title = chat.display_title || directMember?.username || chat.title;
    const imageSrc = chat.display_avatar?.small_url || (directMember ? getAvatarUrl(directMember, "small") : "../../../assets/chat.svg");
    const lastMessagePreview = buildLastMessagePreview(chat.last_message);
    const lastMessageAt = chat.last_message_at || chat.last_message?.created_at;
    const unreadCount = chat.unread_count || 0;

    return (
        <NavLink className={`chat-list-item${unreadCount > 0 ? " unread" : ""}`} ref={ref} to={`/chats/@${chat.chat_id}`}>
            <img
                className="chat-image"
                src={imageSrc}
                alt={`${title}`}
                onError={(event) => {
                    event.currentTarget.src = "../../../assets/chat.svg";
                }}
            />
            <div className="info">
                <div className="chat-list-item-header">
                    <div className="title">{title}</div>
                    <div className="time">{formatChatTime(lastMessageAt)}</div>
                </div>
                <div className="chat-list-item-footer">
                    <div className={`last-message${lastMessagePreview.isAttachmentOnly ? " attachment-preview" : ""}`}>
                        {lastMessagePreview.text}
                    </div>
                    {unreadCount > 0 && <div className="unread-count">{unreadCount}</div>}
                </div>
            </div>
        </NavLink>
    )
})

export default ChatListItem;
