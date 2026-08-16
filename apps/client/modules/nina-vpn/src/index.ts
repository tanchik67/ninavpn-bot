import { NativeModulesProxy, requireNativeModule } from "expo-modules-core";

type Status = "disconnected" | "connecting" | "connected" | "unavailable";

type NinaVpnModuleType = {
  isSupported(): Promise<boolean>;
  prepare(): Promise<boolean>;
  connect(uri: string, nodeId: string): Promise<void>;
  disconnect(): Promise<void>;
  getStatus(): Promise<Status>;
  tcpPingMs?(host: string, port: number, timeoutMs: number): Promise<number>;
};

let mod: NinaVpnModuleType | null = null;
try {
  mod = requireNativeModule<NinaVpnModuleType>("NinaVpn");
} catch {
  mod = (NativeModulesProxy as any).NinaVpn ?? null;
}

export default mod;
