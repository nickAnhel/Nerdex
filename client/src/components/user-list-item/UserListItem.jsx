import { useState, useContext, forwardRef } from "react";
import { Link } from "react-router-dom";
import "./UserListItem.css"

import { StoreContext } from "../..";
import UserService from "../../service/UserService";

import Loader from "../loader/Loader";


const UserListItem = forwardRef((props, ref) => {
    const { store } = useContext(StoreContext);

    const [imgSrc, setImgSrc] = useState(`${process.env.REACT_APP_STORAGE_URL}PPm@${props.user.user_id}?${performance.now()}`);

    const [isLoadingSubscribe, setIsLoadingSubscribe] = useState(false);
    const [isSubscribed, setIsSubsctribed] = useState(props.user.is_subscribed);
    const [subsCount, setSubsCount] = useState(props.user.subscribers_count);

    const handleSubscribe = async () => {
        setIsLoadingSubscribe(true);

        try {
            await UserService.subscribeToUser(props.user.user_id);
            setIsSubsctribed(true);
            setSubsCount((prev) => prev + 1);

        } catch (e) {
            console.log(e);
            // alertsContext.addAlert({
            //     text: "Failed to subscribe to channel",
            //     time: 2000,
            //     type: "error"
            // })
            return;
        }

        setIsLoadingSubscribe(false);
        // alertsContext.addAlert({
        //     text: "Successfully subscribed to channel",
        //     time: 2000,
        //     type: "success"
        // })
    }

    const handleUnsubscribe = async () => {
        setIsLoadingSubscribe(true);

        try {
            await UserService.unsubscribFromuser(props.user.user_id);
            setIsSubsctribed(false);
            setSubsCount((prev) => prev - 1);

        } catch (e) {
            // alertsContext.addAlert({
            //     text: "Failed to unsubscribe from channel",
            //     time: 2000,
            //     type: "error"
            // })
            console.log(e);
        }

        setIsLoadingSubscribe(false);
        // alertsContext.addAlert({
        //     text: "Successfully unsubscribed from channel",
        //     time: 2000,
        //     type: "success"
        // })
    }

    return (
        <Link className="user-list-item" ref={ref} to={`/people/@${props.user.username}`}>
            <div className="left">
                <img
                    className="user-profile-photo"
                    src={imgSrc}
                    onError={() => { setImgSrc("../../../assets/profile.svg") }}
                    alt={`${props.user.username} profile photo`}
                />
                <div className="info">
                    <div className="username">{props.user.username}</div>
                    <div className="subs">{subsCount.toLocaleString()} subscriber{subsCount == 1 ? "" : "s"}</div>
                </div>
            </div>
            <div className="right">
                {

                    isSubscribed ?
                        <button
                            className="btn unsubscribe"
                            onClick={(e) => {
                                e.preventDefault();
                                handleUnsubscribe();
                            }}
                            disabled={!store.isAuthenticated}
                        >
                            {isLoadingSubscribe ? <Loader /> : "Unsubscribe"}
                        </button>
                        :
                        <button
                            className="btn"
                            onClick={(e) => {
                                e.preventDefault();
                                handleSubscribe();
                            }}
                            disabled={!store.isAuthenticated || store.user.user_id == props.user.user_id}
                        >
                            {isLoadingSubscribe ? <Loader /> : "Subscribe"}
                        </button>


                }

            </div>
        </Link>
    )
})

export default UserListItem;