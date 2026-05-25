# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(['..\\src\\horizon6_autogear\\gui.py'],
             pathex=['..\\src'],
             binaries=[],
             datas=[
                 ("..\\web", "web"),
                 ("..\\data\\cars", "data/cars"),
                 ("AppWindowSplash.bmp", "."),
             ],
             hiddenimports=[
                 'horizon6_autogear',
                 'horizon6_autogear.config',
                 'horizon6_autogear.config.config',
                 'horizon6_autogear.core',
                 'horizon6_autogear.core.car_info',
                 'horizon6_autogear.core.forza',
                 'horizon6_autogear.shifting',
                 'horizon6_autogear.shifting.gear_helper',
                 'horizon6_autogear.shifting.keyboard',
                 'horizon6_autogear.utils',
                 'horizon6_autogear.utils.helper',
                 'horizon6_autogear.utils.logger',
                 'horizon6_autogear.utils.path_utils',
                 'horizon6_autogear.core.forza_data_packet',
                 'pynput',
                 'matplotlib',
                 'numpy',
                 'win32api',
                 'win32con',
                 'webview',
                 'webview.platforms',
                 'webview.platforms.winforms',
             ],
             hookspath=[],
             hooksconfig={},
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)

splash = Splash('AppWindowSplash.bmp',
                binaries=a.binaries,
                datas=a.datas,
                text_color='white')

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          splash,
          [],
          name='Horizon6AutoGear',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          icon='FAG.ico',
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None )
