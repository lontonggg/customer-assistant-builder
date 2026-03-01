const AUTH_KEY = "mock_google_auth_user";

export type MockUser = {
  name: string;
  email: string;
  picture: string;
};

export function getMockUser(): MockUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(AUTH_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as MockUser;
    if (!parsed?.email) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function isMockLoggedIn(): boolean {
  return getMockUser() !== null;
}

export function mockLoginWithGoogle(): MockUser {
  const fakeUser: MockUser = {
    name: "Google User",
    email: "user@gmail.com",
    picture: "https://www.gstatic.com/images/branding/product/1x/avatar_square_blue_512dp.png",
  };
  if (typeof window !== "undefined") {
    window.localStorage.setItem(AUTH_KEY, JSON.stringify(fakeUser));
  }
  return fakeUser;
}

export function mockLogout(): void {
  if (typeof window !== "undefined") {
    window.localStorage.removeItem(AUTH_KEY);
  }
}
