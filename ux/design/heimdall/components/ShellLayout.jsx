
interface ShellLayoutProps extends React.HTMLAttributes<HTMLDivElement> {
  titlebar?: TitlebarProps & { hide?: boolean }
  appTitle?: AppTitleProps & { hide?: boolean }
  topbar?: TopbarProps & { hide?: boolean }
  sidebar?: SidebarProps & { hide?: boolean }
  statusbar?: StatusbarProps & { hide?: boolean }
}

const ShellLayout = React.forwardRef<HTMLDivElement, ShellLayoutProps>(
  (
    {
      titlebar,
      appTitle,
      topbar,
      sidebar,
      statusbar,
      children,
      className = '',
      ...props
    },
    ref
  ) => {
    const classNames = ['shell-layout', className].filter(Boolean).join(' ')

    const { hide: _titlebarHide, ...titlebarProps } = titlebar ?? {} as TitlebarProps & { hide?: boolean }
    const renderTitlebar = titlebar && !titlebar.hide

    const { hide: _appTitleHide, ...appTitleProps } = appTitle ?? {} as AppTitleProps & { hide?: boolean }
    const renderAppTitle = appTitle && !appTitle.hide

    const { hide: _topbarHide, ...topbarProps } = topbar ?? {} as TopbarProps & { hide?: boolean }
    const renderTopbar = topbar && !topbar.hide

    const { hide: _sidebarHide, ...sidebarProps } = sidebar ?? {} as SidebarProps & { hide?: boolean }
    const renderSidebar = sidebar && !sidebar.hide

    const { hide: _statusbarHide, ...statusbarProps } = statusbar ?? {} as StatusbarProps & { hide?: boolean }
    const renderStatusbar = statusbar && !statusbar.hide

    const sidebarCollapsed = sidebarProps.collapsed ?? false

    return (
      <div ref={ref} className={classNames} {...props}>
        {renderTitlebar && <Titlebar {...titlebarProps} />}
        <div className="shell-layout__main">
          {renderSidebar ? (
            <div className="shell-layout__sidebar-col">
              {renderAppTitle && (
                <AppTitle {...appTitleProps} collapsed={sidebarCollapsed} />
              )}
              <Sidebar {...sidebarProps} />
            </div>
          ) : renderAppTitle ? (
            <AppTitle {...appTitleProps} />
          ) : null}
          <div className="shell-layout__content">
            {renderTopbar && <Topbar {...topbarProps} />}
            <main className="shell-layout__canvas">{children}</main>
          </div>
        </div>
        {renderStatusbar && <Statusbar {...statusbarProps} />}
      </div>
    )
  }
)

ShellLayout.displayName = 'ShellLayout'



// --- Babel-standalone: expose runtime values to window ---
window.ShellLayout = ShellLayout;
