import React from 'react';

interface MainContentProps {
  children: React.ReactNode;
}

const MainContent: React.FC<MainContentProps> = ({ children }) => {
  // flexGrow is handled by the parent div in App.tsx
  return (
    <main style={{ padding: '1rem', width: '100%' }}>
      {children}
    </main>
  );
};

export default MainContent;
