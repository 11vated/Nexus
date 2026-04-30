import { ChatPanel } from '../components/ChatPanel';

interface ChatPageProps {
  workspace: string;
}

export function ChatPage({ workspace }: ChatPageProps) {
  return (
    <div className="page chat-page">
      <h1>Chat with Nexus</h1>
      <ChatPanel workspace={workspace} />
    </div>
  );
}
