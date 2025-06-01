import { useContext } from "react";
import "./Profile.css";

import { StoreContext } from "../..";

import Unauthorized from "../../components/unauthorized/Unauthorized";
import ProfileForm from "../../components/profile-form/ProfileForm";


function Profile() {
    const { store } = useContext(StoreContext);

    if (!store.isAuthenticated) {
        return (
            <div id="profile">
                <Unauthorized />
            </div>
        )
    }

    return (
        <div id="profile">
            <ProfileForm />
        </div>
    )
}

export default Profile;