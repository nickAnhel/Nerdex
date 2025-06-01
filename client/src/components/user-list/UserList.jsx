import { useState, createRef, useRef, useEffect } from "react";
import { useQuery } from "@siberiacancode/reactuse";
import "./UserList.css"

import UserListItem from "../user-list-item/UserListItem";
import Loader from "../loader/Loader";


const USERS_IN_PORTION = 5;


function UserList({ fetchUsers, filters, refresh }) {
    const lastItem = createRef();
    const observerLoader = useRef();

    const [users, setUsers] = useState([]);
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
                limit: USERS_IN_PORTION,
            }
            const res = await fetchUsers(params);
            return res.data;
        },
        {
            keys: [offset, refresh],
            onSuccess: (fetchedUsers) => {
                setUsers((prevUsers) => [...prevUsers, ...fetchedUsers]);
            }

        }
    );

    const actionInSight = (entries) => {
        if (entries[0].isIntersecting && offset < USERS_IN_PORTION * 10) {
            setOffset((prev) => prev + USERS_IN_PORTION);
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
        <div className="user-list">
            <div className="users">
                {
                    users.map((user, index) => {
                        if (index + 1 == users.length) {
                            return <UserListItem key={user.user_id} user={user} ref={lastItem}/>
                        }
                        return <UserListItem key={user.user_id} user={user} />
                    })
                }
                {
                    (!isLoading && users.length == 0) ? <div className="hint">No users</div> : ""
                }
            </div>

            {
                isLoading &&
                <div className="loader"><Loader /></div>
            }
        </div>
    )
}

export default UserList;