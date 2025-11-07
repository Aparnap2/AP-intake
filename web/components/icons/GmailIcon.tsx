interface GmailIconProps {
  className?: string;
}

export const GmailIcon = ({ className }: GmailIconProps) => (
  <svg className={className} viewBox="0 0 24 24" fill="none">
    <path d="M6 12C6 10.89 6.89 10 8 10H16C17.11 10 18 10.89 18 12V20H6V12Z" fill="#EA4335"/>
    <path d="M20 6L12 13L4 6H20Z" fill="#34A853"/>
    <path d="M20 6V18C20 19.1 19.1 20 18 20H6C4.9 20 4 19.1 4 18V6C4 4.9 4.9 4 6 4H18C19.1 4 20 4.9 20 6Z" fill="#4285F4"/>
    <path d="M12 13L4 6V18L12 13Z" fill="#FBBC05"/>
  </svg>
)