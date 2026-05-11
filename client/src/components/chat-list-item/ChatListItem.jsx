import { forwardRef, useContext } from "react";
import { NavLink } from "react-router-dom";

import "./ChatListItem.css"

import { StoreContext } from "../..";
import { getAvatarUrl } from "../../utils/avatar";


const ChatListItem = forwardRef((props, ref) => {
    const { store } = useContext(StoreContext);
    const chat = props.chat;
    const directMember = chat.chat_type === "direct"
        ? chat.members?.find((member) => member.user_id !== store.user.user_id)
        : null;
    const title = directMember?.username || chat.title;
    const imageSrc = directMember ? getAvatarUrl(directMember, "small") : "../../../assets/chat.svg";

    return (
        <NavLink className="chat-list-item" ref={ref} to={`/chats/@${chat.chat_id}`}>
            <img
                className="chat-image"
                src={imageSrc}
                alt={`${title}`}
                onError={(event) => {
                    event.currentTarget.src = "../../../assets/chat.svg";
                }}
            />
            <div className="info">
                <div className="title">{title}</div>
            </div>
        </NavLink>
    )
})

export default ChatListItem;
