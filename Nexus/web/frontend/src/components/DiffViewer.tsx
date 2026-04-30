export function DiffViewer({ diff }: { diff: string }) {
  return (
    <div className="diff-viewer">
      <pre className="diff-content">{diff}</pre>
    </div>
  );
}

export function ProjectMap({ workspace }: { workspace: string }) {
  return (
    <div className="project-map">
      <h3>Project Structure</h3>
      <p>Workspace: {workspace}</p>
      <div className="file-tree">
        <p>File tree visualization coming soon...</p>
      </div>
    </div>
  );
}
