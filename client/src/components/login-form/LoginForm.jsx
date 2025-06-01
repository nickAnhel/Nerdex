import { useState, useContext, useRef, useEffect } from "react"
import { observer } from "mobx-react-lite";
import { Link, useNavigate } from "react-router-dom";
import "./LoginForm.css"

import { StoreContext } from "../../"
import Loader from "../loader/Loader";


const LoginForm = () => {
    const { store } = useContext(StoreContext);
    const navigate = useNavigate();

    const [isLoading, setIsLoading] = useState(false);
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");

    const usernameInputRef = useRef(null);

    useEffect(() => {
        if (username === "") {
            usernameInputRef?.current?.focus();
        }
    }, [username])

    const handleSubmit = async (e) => {
        setIsLoading(true);
        e.preventDefault();

        try {
            await store.login(username, password);
            navigate("/");
        } catch (e) {
            console.log(e);
            console.log(e?.response?.data?.detail);
        }

        setIsLoading(false);
    }

    return (
        <div className="login-form">
            <h1>Sign In</h1>

            <form onSubmit={(e) => { handleSubmit(e); }}>

                <input
                    ref={usernameInputRef}
                    id="username"
                    type="text"
                    placeholder="Username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                />


                <input
                    id="password"
                    type="password"
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                />

                <button
                    type="submit"
                    disabled={isLoading}
                >
                    { isLoading ? <Loader /> : "Sign In"}
                </button>
                <div className="hint">Don't have an account? <Link to="/signup">Sign Up</Link></div>
            </form>
        </div>
    )
}

export default observer(LoginForm);