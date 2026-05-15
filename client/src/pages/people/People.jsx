import { useState } from "react";
import { useNavigate } from "react-router-dom";

import "./People.css";

import UserService from "../../service/UserService";

import GlobalSearchInput from "../../components/global-search-input/GlobalSearchInput";
import UserList from "../../components/user-list/UserList";


function People() {
    const navigate = useNavigate();
    const [searchQuery, setSearchQuery] = useState("");

    return (
        <div id="people">
            <GlobalSearchInput
                value={searchQuery}
                onChange={setSearchQuery}
                onSubmit={(query) => navigate(`/search?q=${encodeURIComponent(query)}&type=author`)}
                placeholder="Search creators"
            />
            <UserList fetchUsers={UserService.getUsers} filters={{ desc: true, order: "subscribers_count" }} />
        </div>
    )
}

export default People;
