import { useState, createRef, useRef, useEffect } from "react";
import { useQuery } from "@siberiacancode/reactuse";
import "./ChatList.css"

import Loader from "../loader/Loader";

import ChatListItem from "../chat-list-item/ChatListItem";


const CHATS_IN_PORTION = 5;


function ChatList({ fetchChats, filters, refresh }) {
    const lastItem = createRef();
    const observerLoader = useRef();

    const [chats, setUsers] = useState([]);
    const [offset, setOffset] = useState(0);



    useEffect(() => {
        setOffset(0);
        setUsers([]);
    }, [refresh]);

    const { isLoading, isError, isSuccess, error } = useQuery(
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
                setUsers((prevChats) => [...prevChats, ...fetchedChats]);
            }

        }
    );

    const actionInSight = (entries) => {
        if (entries[0].isIntersecting && offset < CHATS_IN_PORTION * 10) {
            setOffset((prev) => prev + CHATS_IN_PORTION);
        }
    };

    useEffect(() => {
        if (observerLoader.current) {
            observerLoader.current.disconnect();
        }

        observerLoader.current = new IntersectionObserver(actionInSight);

        if (lastItem.current) {
            observerLoader.current.observe(lastItem.current);
        }
    }, [lastItem]);

    if (isError) {
        console.log(error);
        return;
    }


    return (
        <div className="chat-list">

            <div className="chats">
                {
                    chats.map((chat, index) => {
                        if (index + 1 == chats.length) {
                            return <ChatListItem key={chat.chat_id} chat={chat} ref={lastItem}/>
                        }
                        return <ChatListItem key={chat.chat_id} chat={chat} />
                    })
                }
                {
                    (!isLoading && chats.length == 0) ? <div className="hint">No chats</div> : ""
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