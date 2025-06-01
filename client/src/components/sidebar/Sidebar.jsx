import { useContext, useState, useEffect } from "react";
import { Link, NavLink } from "react-router-dom"
import { observer } from "mobx-react-lite";

import "./Sidebar.css"

import { StoreContext } from "../..";


function Sidebar() {
    const { store } = useContext(StoreContext);

    const [imgSrc, setImgSrc] = useState(null);

    useEffect(() => {
        setImgSrc(`${process.env.REACT_APP_STORAGE_URL}PPs@${store.user.user_id}?${performance.now()}`);
    }, [store.user?.user_id, store.isChangedProfilePhoto])

    return (
        <div id="sidebar">
            <div id="sidebar-top">
                <NavLink to="/people" className="sidebar-item" >
                    <img src="/assets/people.svg" alt="People" />
                    People
                </NavLink>
                <NavLink to="/feed" className="sidebar-item">
                    <img src="/assets/feed.svg" alt="Feed" />
                    Feed
                </NavLink>
                <NavLink to="/chats" className="sidebar-item">
                    <img src="/assets/chats.svg" alt="Chats" />
                    Chats
                </NavLink>
            </div>

            <div id="sidebar-bottom">
                {/* <NavLink to="/settings" className="sidebar-item">
                    <img src="/assets/settings.svg" alt="Settings" />
                </NavLink> */}

                {
                    store.isAuthenticated
                        ?
                        <Link to="/profile" className="sidebar-item">
                            <img
                                className="profile"
                                src={imgSrc}
                                onError={() => { setImgSrc("../../../assets/profile.svg") }}
                                alt="Profile"
                            />
                        </Link>
                        :
                        <Link to="/login" className="sidebar-item">
                            <img src="/assets/login.svg" alt="Login" />
                        </Link>
                }
            </div>
        </div>
    );
}

export default observer(Sidebar);