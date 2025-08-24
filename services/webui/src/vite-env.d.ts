/// <reference types="vite/client" />

declare module 'react' {
  export = React;
  export as namespace React;
  namespace React {
    type ReactNode = any;
    interface FC<P = {}> {
      (props: P): JSX.Element | null;
    }
    function useState<S>(initialState: S | (() => S)): [S, (value: S | ((prevState: S) => S)) => void];
    function useEffect(effect: () => void | (() => void), deps?: any[]): void;
    function useRef<T>(initialValue: T): { current: T };
    interface ChangeEvent<T = Element> {
      target: T & { value: string; type: string; checked: boolean };
    }
  }
}

declare module 'react/jsx-runtime' {
  export function jsx(type: any, props: any, key?: any): any;
  export function jsxs(type: any, props: any, key?: any): any;
  export function Fragment(props: { children?: any }): any;
}

declare module 'react-dom/client' {
  export function createRoot(container: Element): {
    render(element: any): void;
  };
}

declare module 'react-router-dom' {
  export function BrowserRouter(props: { children: any }): JSX.Element;
  export function Routes(props: { children: any }): JSX.Element;
  export function Route(props: { path: string; element: JSX.Element }): JSX.Element;
  export function Link(props: { to: string; style?: any; children: any }): JSX.Element;
  export function Navigate(props: { to: string; replace?: boolean }): JSX.Element;
  export function useLocation(): { pathname: string };
}
