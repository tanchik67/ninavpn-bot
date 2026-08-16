package store.ninavpn.app

import android.graphics.Color
import android.os.Build
import android.os.Bundle
import android.view.View

import com.facebook.react.ReactActivity
import com.facebook.react.ReactActivityDelegate
import com.facebook.react.defaults.DefaultNewArchitectureEntryPoint.fabricEnabled
import com.facebook.react.defaults.DefaultReactActivityDelegate

import expo.modules.ReactActivityDelegateWrapper
import store.ninavpn.vpn.NinaVpnAutoConnect

class MainActivity : ReactActivity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    // Keep splash drawable as window background (AppTheme) — no white flash.
    setTheme(R.style.AppTheme)
    super.onCreate(null)
    window.statusBarColor = Color.BLACK
    window.navigationBarColor = Color.BLACK
    window.decorView.setBackgroundColor(Color.BLACK)
    // RN root view defaults to white until the first JS frame
    findViewById<View>(android.R.id.content)?.setBackgroundColor(Color.BLACK)
  }

  override fun onUserLeaveHint() {
    NinaVpnAutoConnect.onUserLeave()
    super.onUserLeaveHint()
  }

  override fun onPause() {
    NinaVpnAutoConnect.onPause()
    super.onPause()
  }

  override fun onResume() {
    super.onResume()
    NinaVpnAutoConnect.onResume(this)
  }

  /**
   * Returns the name of the main component registered from JavaScript. This is used to schedule
   * rendering of the component.
   */
  override fun getMainComponentName(): String = "main"

  /**
   * Returns the instance of the [ReactActivityDelegate]. We use [DefaultReactActivityDelegate]
   * which allows you to enable New Architecture with a single boolean flags [fabricEnabled]
   */
  override fun createReactActivityDelegate(): ReactActivityDelegate {
    return ReactActivityDelegateWrapper(
          this,
          BuildConfig.IS_NEW_ARCHITECTURE_ENABLED,
          object : DefaultReactActivityDelegate(
              this,
              mainComponentName,
              fabricEnabled
          ){})
  }

  /**
    * Align the back button behavior with Android S
    * where moving root activities to background instead of finishing activities.
    * @see <a href="https://developer.android.com/reference/android/app/Activity#onBackPressed()">onBackPressed</a>
    */
  override fun invokeDefaultOnBackPressed() {
      if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.R) {
          if (!moveTaskToBack(false)) {
              // For non-root activities, use the default implementation to finish them.
              super.invokeDefaultOnBackPressed()
          }
          return
      }

      // Use the default back button implementation on Android S
      // because it's doing more than [Activity.moveTaskToBack] in fact.
      super.invokeDefaultOnBackPressed()
  }
}
