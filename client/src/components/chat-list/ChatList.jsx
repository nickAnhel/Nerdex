import { useCallback, useState, useRef, useEffect, useContext } from "react";
import { useQuery } from "@siberiacancode/reactuse";
import { useParams } from "react-router-dom";
import { io } from "socket.io-client";
import "./ChatList.css"

import { StoreContext } from "../..";
import Loader from "../loader/Loader";

import ChatListItem from "../chat-list-item/ChatListItem";


const CHATS_IN_PORTION = 5;


function parseSocketPayload(data) {
    return typeof data === "string" ? JSON.parse(data) : data;
}

function sortDialogs(chats) {
    return [...chats].sort((a, b) => {
        const aTime = a.last_message_at || a.last_message?.created_at;
        const bTime = b.last_message_at || b.last_message?.created_at;

        if (!aTime && !bTime) {
            return a.chat_id.localeCompare(b.chat_id);
        }
        if (!aTime) {
            return 1;
        }
        if (!bTime) {
            return -1;
        }

        return new Date(bTime).getTime() - new Date(aTime).getTime();
    });
}

function mergeChats(prevChats, fetchedChats) {
    const byId = new Map(prevChats.map((chat) => [chat.chat_id, chat]));
    fetchedChats.forEach((chat) => {
        byId.set(chat.chat_id, {
            ...byId.get(chat.chat_id),
            ...chat,
        });
    });
    return sortDialogs(Array.from(byId.values()));
}

function ChatList({ fetchChats, filters, refresh, enableRealtime = true }) {
    const { store } = useContext(StoreContext);
    const params = useParams();
    const lastItem = useRef(null);
    const observerLoader = useRef();
    const socket = useRef(null);

    const [chats, setChats] = useState([]);
    const [offset, setOffset] = useState(0);
    const currentChatId = params.chatId?.startsWith("@")
        ? params.chatId.slice(1)
        : null;
    const chatIds = chats.map((chat) => chat.chat_id).join(":");

    useEffect(() => {
        setOffset(0);
        setChats([]);
    }, [refresh]);

    useEffect(() => {
        if (!currentChatId) {
            return;
        }

        setChats((prevChats) => prevChats.map((chat) => (
            chat.chat_id === currentChatId
                ? { ...chat, unread_count: 0 }
                : chat
        )));
    }, [currentChatId]);

    const { isLoading, isError, error } = useQuery(
        async () => {
            const params = {
                ...filters,
                offset: offset,
                limit: CHATS_IN_PORTION,
            }
            const res = await fetchChats(params);
            return res.data;
        },
        {
            keys: [offset, refresh],
            onSuccess: (fetchedChats) => {
                setChats((prevChats) => mergeChats(prevChats, fetchedChats));
            }

        }
    );

    useEffect(() => {
        if (!enableRealtime || !chatIds) {
            return;
        }

        const joinedChatIds = chatIds ? chatIds.split(":") : [];

        socket.current = io(process.env.REACT_APP_WS_HOST, {
            path: "/ws",
            transports: ["websocket"],
            upgrade: false,
            auth: {
                token: localStorage.getItem("token"),
            },
        });

        joinedChatIds.forEach((chatId) => {
            socket.current.emit("join", { chat_id: chatId });
        });

        socket.current.on("message:created", (data) => {
            const msgData = parseSocketPayload(data);
            setChats((prevChats) => sortDialogs(prevChats.map((chat) => {
                if (chat.chat_id !== msgData.chat_id) {
                    return chat;
                }

                const isCurrentChat = chat.chat_id === currentChatId;
                const isOwnMessage = msgData.user_id === store.user.user_id;

                return {
                    ...chat,
                    last_message: {
                        message_id: msgData.message_id,
                        chat_id: msgData.chat_id,
                        client_message_id: msgData.client_message_id,
                        content: msgData.content,
                        attachments: msgData.attachments || [],
                        created_at: msgData.created_at,
                        user_id: msgData.user_id,
                    },
                    last_message_at: msgData.created_at,
                    unread_count: isCurrentChat
                        ? 0
                        : isOwnMessage
                            ? (chat.unread_count || 0)
                            : (chat.unread_count || 0) + 1,
                };
            })));
        });

        return () => {
            joinedChatIds.forEach((chatId) => {
                socket.current?.emit("leave", { chat_id: chatId });
            });
            socket.current?.off("message:created");
            socket.current?.disconnect();
        };
    }, [enableRealtime, chatIds, currentChatId, store.user.user_id]);

    const actionInSight = useCallback((entries) => {
        if (entries[0].isIntersecting && offset < CHATS_IN_PORTION * 10) {
            setOffset((prev) => prev + CHATS_IN_PORTION);
        }
    }, [offset]);

    useEffect(() => {
        if (observerLoader.current) {
            observerLoader.current.disconnect();
        }

        observerLoader.current = new IntersectionObserver(actionInSight);

        if (lastItem.current) {
            observerLoader.current.observe(lastItem.current);
        }
    }, [actionInSight, chats]);

    if (isError) {
        console.log(error);
        return;
    }


    return (
        <div className="chat-list">

            <div className="chats">
                {
                    chats.map((chat, index) => {
                        if (index + 1 === chats.length) {
                            return <ChatListItem key={chat.chat_id} chat={chat} ref={lastItem}/>
                        }
                        return <ChatListItem key={chat.chat_id} chat={chat} />
                    })
                }
                {
                    (!isLoading && chats.length === 0) ? <div className="hint">No chats</div> : ""
                }
            </div>

            {
                isLoading &&
                <div className="loader"><Loader /></div>
            }


        </div>
    )
}

export default ChatList;
