import { useContext } from "react";
import { Link, NavLink } from "react-router-dom"
import { observer } from "mobx-react-lite";

import "./Sidebar.css"

import { StoreContext } from "../..";
import { getAvatarRenderKey, getAvatarUrl } from "../../utils/avatar";


function Sidebar() {
    const { store } = useContext(StoreContext);
    const avatarSrc = getAvatarUrl(store.user, "small");
    const avatarRenderKey = getAvatarRenderKey(store.user, "small");

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
                <NavLink to="/articles" className="sidebar-item">
                    <img src="/assets/articles.svg" alt="Articles" />
                    Articles
                </NavLink>
                <NavLink to="/videos" className="sidebar-item">
                    <img src="/assets/videos.svg" alt="Videos" />
                    Videos
                </NavLink>
                <NavLink to="/courses" className="sidebar-item">
                    <img src="/assets/courses.svg" alt="Courses" />
                    Courses
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
                                key={avatarRenderKey}
                                className="profile"
                                src={avatarSrc}
                                onError={(e) => { e.currentTarget.src = "/assets/profile.svg"; }}
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
