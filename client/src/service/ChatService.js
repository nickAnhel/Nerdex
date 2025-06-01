import api from "../http";


export default class ChatService {
    static async createChat(chatId, data) {
        return api.post("/chats", data);
    }

    static async getChatById(chatId) {
        return api.get(`/chats/${chatId}`);
    }

    static async searchChats(params) {
        return api.get("/chats/search", { params });
    }

    static async updateChat(chatId, data) {
        return api.patch(`/chats/${chatId}`, data);
    }

    static async joinChat(chatId) {
        return api.post(`/chats/${chatId}/join`);
    }

    static async leaveChat(chatId) {
        return api.delete(`/chats/${chatId}/leave`);
    }

    static async getChatHistory(chatId) {
        return api.get(`/chats/${chatId}/history`);
    }

    static async getUserJoinedChats(params) {
        return api.get("/chats/user", { params });
    }

    static async deleteChat(chatId) {
        return api.delete(`/chats/${chatId}`);
    }
}