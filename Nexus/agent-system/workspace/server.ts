import express from 'express';

const app = express();
const port = 3000;

app.get('/hello', (req, res) => {
  res.json({ message: "Hello, World!" });
});

app.get('/goodbye', (req, res) => {
  const name = (req.query.name as string) || 'World';
  res.json({ message: `Goodbye, ${name}!` });
});

app.listen(port, () => {
  console.log(`Server running at http://localhost:${port}`);
});

export default app;