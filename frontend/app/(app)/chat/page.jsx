// app/(app)/chat/page.jsx
import { redirect } from "next/navigation";

export default function ChatPage() {
  redirect("/chat/new");
}