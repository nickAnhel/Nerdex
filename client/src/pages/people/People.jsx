import "./People.css";

import UserService from "../../service/UserService";

import Search from "../../components/search/Search";
import UserList from "../../components/user-list/UserList";


function People() {
    return (
        <div id="people">
            <Search searchScope={"people"} />
            <UserList fetchUsers={UserService.getUsers} filters={{ desc: true, order: "subscribers_count" }} />
        </div>
    )
}

export default People;