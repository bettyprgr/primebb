export type ToolDefinition = {
  id: string;
  name: string;
  description: string;
  status: "available" | "coming_soon";
  route: string;
  primaryActionLabel: string;
};

export const tools: ToolDefinition[] = [
  {
    id: "social-pumper",
    name: "Social Pumper",
    description: "Authenticate Gmail and connect accounts to YouTube, Quora, Reddit, X, and eBay through Google OAuth.",
    status: "available",
    route: "/tools/social-pumper",
    primaryActionLabel: "Open workspace",
  },
  {
    id: "amazon-creation",
    name: "Amazon Creation",
    description: "Register Amazon accounts via phone number and SMS OTP, with automatic captcha solving.",
    status: "available",
    route: "/tools/amazon-creation",
    primaryActionLabel: "Open workspace",
  },
];
