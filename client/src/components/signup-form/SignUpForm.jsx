import { useState, useContext, useRef, useEffect } from "react"
import { observer } from "mobx-react-lite";
import { Link, useNavigate } from "react-router-dom";
import "./SignUpForm.css"

import { StoreContext } from "../../"
import Loader from "../loader/Loader";


const SignUpForm = () => {
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
        e.preventDefault();

        if (!/^[A-Za-z0-9._-]{1,32}$/.test(username)) {
            alert("Invalid username");
            return;
        }

        setIsLoading(true);

        try {
            await store.register(
                {
                    username: username.trim(),
                    password,
                }
            );
            navigate("/");
        } catch (e) {
            console.log(e);
            console.log(e?.response?.data?.detail);
        }

        setIsLoading(false);
    }

    return (
        <div className="singup-form">
            <h1>Sign Up</h1>

            <form onSubmit={(e) => { handleSubmit(e); }}>

                <input
                    ref={usernameInputRef}
                    id="username"
                    type="text"
                    placeholder="Username"
                    value={username}
                    pattern="^[A-Za-z0-9._-]{1,32}$"
                    maxLength={32}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                />

                <input
                    id="password"
                    type="password"
                    placeholder="Password"
                    value={password}
                    minLength={8}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                />

                <button
                    type="submit"
                    disabled={isLoading}
                >
                    { isLoading ? <Loader /> : "Sign Up"}
                </button>

                <div className="hint">Already have an account? <Link to="/login">Sign In</Link></div>
            </form>
        </div>
    )
}

export default observer(SignUpForm);