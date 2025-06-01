import { forwardRef } from "react";
import { NavLink } from "react-router-dom";

import "./ChatListItem.css"


const ChatListItem = forwardRef((props, ref) => {
    return (
        <NavLink className="chat-list-item" ref={ref} to={`/chats/@${props.chat.chat_id}`}>
            <img
                className="chat-image"
                src="../../../assets/chat.svg"
                alt={`${props.chat.title}`}
            />
            <div className="info">
                <div className="title">{props.chat.title}</div>
            </div>
        </NavLink>
    )
})

export default ChatListItem;