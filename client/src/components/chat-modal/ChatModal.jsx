import { useEffect, useState } from "react";

import "./ChatModal.css"

import Modal from "../modal/Modal";
import Loader from "../loader/Loader";


function ChatModal({
    active,
    setActive,

    chatId,
    title,
    isPrivate,
    setTitle,
    saveChatFunc,

    modalHeader,
    buttonText
}) {
    const [chatTitle, setChatTitle] = useState(title || "");
    const [isLoadingSaveChat, setIsLoadingSaveChat] = useState(false);

    const [chatIsPrivate, setChatIsPrivate] = useState(isPrivate);

    const handleSaveChat = async (event) => {
        setIsLoadingSaveChat(true);
        event.preventDefault();

        try {
            const chatData = {
                title: chatTitle,
                is_private: chatIsPrivate,
            }
            await saveChatFunc(chatId, chatData);

            if (setTitle) {
                setTitle(chatTitle);
            }

        } catch (e) {
            console.log(e);
            console.log(e?.response?.data?.detail);

        } finally {
            setIsLoadingSaveChat(false);
            setActive(false);
        }
    }

    return (
        <Modal active={active} setActive={setActive}>
            <form id="save-chat-form">
                <h1>{modalHeader}</h1>

                <input
                    type="text"
                    placeholder="Chat title"
                    value={chatTitle}
                    onChange={(e) => setChatTitle(e.target.value)}
                />

                <div className="chat-private">
                    <input
                        type="checkbox"
                        id="private"
                        name="private"
                        value="1"
                        required
                        checked={chatIsPrivate}
                        onChange={(e) => setChatIsPrivate(e.target.checked)}
                    />
                    <label htmlFor="private" className="chat">Private</label>
                </div>

                <button
                    disabled={chatTitle.trim().length < 1}
                    onClick={(e) => { handleSaveChat(e); }}
                >
                    {isLoadingSaveChat ? <Loader /> : buttonText}
                </button>
            </form>
        </Modal>
    )
}

export default ChatModal;