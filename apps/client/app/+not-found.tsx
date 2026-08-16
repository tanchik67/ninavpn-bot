import { Redirect, useGlobalSearchParams, usePathname } from "expo-router";
import * as Linking from "expo-linking";
import { OAuthReturnScreen } from "../src/lib/oauthReturn";

export default function NotFound() {
  const path = usePathname() || "";
  const params = useGlobalSearchParams();
  const url = Linking.useURL() || "";
  const hay = `${path} ${url} ${JSON.stringify(params)}`;

  if (/google-auth/i.test(hay) || params.id_token) {
    return <OAuthReturnScreen kind="google" />;
  }
  if (/tg-auth/i.test(hay) || params.hash) {
    return <OAuthReturnScreen kind="telegram" />;
  }
  return <Redirect href="/" />;
}
