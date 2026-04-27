import { Tabs } from "expo-router";

export default function RootLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: { backgroundColor: "#070b14", borderTopColor: "#1f2a44" },
        tabBarActiveTintColor: "#7cf0c5",
        tabBarInactiveTintColor: "#8b95ad",
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Overview" }} />
      <Tabs.Screen name="studio" options={{ title: "Pocket Studio" }} />
    </Tabs>
  );
}
