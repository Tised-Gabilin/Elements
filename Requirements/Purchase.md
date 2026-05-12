# In-App Purchases (IAP) Module - Technical Implementation Guide

**Template Type:** Reusable technical design pattern  
**Scope:** Flutter app purchase architecture and implementation  
**Package:** in_app_purchase ^3.2.0

## How to Adapt This Template

Before implementation in a new app, replace project-specific values in examples:

- Product IDs (for example `forever_pro`) with your store product IDs.
- App package identifiers with your target app identifiers.
- Feature labels and entitlement naming with your app terminology.
- Pricing and paywall copy with your business model.

`Purchase.md` is a persistent technical template and should remain in the project even when `Initial Research.md` changes.

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Dependencies](#2-dependencies)
3. [Core Purchase Files](#3-core-purchase-files)
4. [BLoC/State Management](#4-blocsstate-management)
5. [UI Components & Widgets](#5-ui-components--widgets)
6. [Theme/Styling Configuration](#6-themestyling-configuration)
7. [Database Configuration](#7-database-configuration)
8. [App Initialization](#8-app-initialization)
9. [Purchase Flow Diagram](#9-purchase-flow-diagram)
10. [Key Implementation Details](#10-key-implementation-details)
11. [Important Configuration](#11-important-configuration)
12. [Error Handling & Debugging](#12-error-handling--debugging)
13. [Testing Checklist](#13-testing-checklist)

---

## 1. Project Structure

Create the following directory structure in your project's `lib/` folder:

```
lib/
├── bloc/
│   └── iap/
│       ├── iap_bloc.dart          # Main BLoC for handling IAP events
│       ├── iap_event.dart         # BLoC events
│       └── iap_state.dart         # BLoC states
├── data/
│   ├── database/
│   │   └── database_helper.dart   # SQLite database operations
│   └── models/
│       ├── iap_product.dart       # Product model
│       ├── purchase_model.dart    # Purchase record model
│       ├── pro_status.dart        # Pro subscription status
│       └── models.dart            # Export file
├── services/
│   └── iap_manager.dart           # Core IAP service (singleton)
├── utils/
│   ├── iap_constants.dart         # Product ID constants
│   └── iap_helpers.dart           # Helper functions
├── ui/
│   ├── widgets/
│   │   └── iap_example_widget.dart # Example UI components
│   └── theme/
│       └── app_theme.dart         # Theme configuration
└── main.dart                       # App initialization
```

---

## 2. Dependencies

Add to your `pubspec.yaml`:

```yaml
dependencies:
  flutter:
    sdk: flutter
  flutter_localizations:
    sdk: flutter

  # State management
  flutter_bloc: ^9.0.0
  equatable: ^2.0.7

  # Local database
  sqflite: ^2.4.2
  path: ^1.9.1

  # In-app purchases
  in_app_purchase: ^3.2.0

  # Shared Preferences (for currency caching)
  shared_preferences: ^2.3.3
```

Then run:
```bash
flutter pub get
```

---

## 3. Core Purchase Files

### 3.1 IAPManager Service (`lib/services/iap_manager.dart`)

This is the **core singleton service** managing all IAP operations.

```dart
import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:in_app_purchase/in_app_purchase.dart';
import '../data/models/models.dart';
import '../data/database/database_helper.dart';
import 'currency_preferences.dart';

/// Product IDs that should match your App Store Connect and Google Play Console configuration
const String foreverProProductId = 'forever_pro';

class IAPManager {
  static final IAPManager _instance = IAPManager._internal();

  final InAppPurchase _inAppPurchase = InAppPurchase.instance;
  final DatabaseHelper _dbHelper = DatabaseHelper.instance;
  final CurrencyPreferences _currencyPrefs = CurrencyPreferences();

  StreamSubscription<List<PurchaseDetails>>? _purchaseStreamSubscription;
  final _proStatusNotifier = ValueNotifier<ProStatus>(ProStatus.notPro());
  /// Incremented when a purchase is canceled or errors out, so the bloc can react.
  final _purchaseCanceledNotifier = ValueNotifier<int>(0);
  bool _hasPrefetchedProducts = false;
  bool _isRestoring = false;
  bool _foundProDuringRestore = false;

  IAPManager._internal();

  factory IAPManager() {
    return _instance;
  }

  /// Stream of pro status changes
  ValueNotifier<ProStatus> get proStatusNotifier => _proStatusNotifier;

  /// Notifier that increments when a purchase is canceled or errors out.
  ValueNotifier<int> get purchaseCanceledNotifier => _purchaseCanceledNotifier;

  /// Initialize the IAP manager - must be called at app startup
  Future<void> initialize() async {
    debugPrint('IAP: Initializing for ${Platform.operatingSystem}...');

    // Load initial pro status from database (cached state)
    final proStatus = await _dbHelper.getProStatus();
    _proStatusNotifier.value = proStatus;
    debugPrint('IAP: Cached pro status: ${proStatus.isPro}');

    // Check if IAP is available
    final available = await _inAppPurchase.isAvailable();
    if (!available) {
      debugPrint('IAP: In-app purchase not available on this device');
      // On iOS simulator, IAP may not be available but we should continue
      if (Platform.isIOS && !kReleaseMode) {
        debugPrint('IAP: Running on iOS in debug mode - this is expected on simulator');
      }
      return;
    }

    debugPrint('IAP: In-app purchase is available');

    // Listen to purchase stream
    _purchaseStreamSubscription?.cancel();
    _purchaseStreamSubscription = _inAppPurchase.purchaseStream.listen(
      (purchaseList) => _handlePurchaseUpdates(purchaseList),
      onError: (error) => debugPrint('IAP Purchase stream error: $error'),
    );

    // Prefetch products once to cache store currency/sign
    await _prefetchProducts();

    // CRITICAL: Restore purchases on startup
    // This queries the App Store (iOS) or Google Play (Android) for all non-consumable purchases
    // If user has purchased forever_pro, it will be returned and processed
    // This is the source of truth - store account, not our local database
    debugPrint('IAP: Checking ${Platform.isIOS ? 'App Store' : 'Google Play'} for existing purchases...');
    await restorePurchases();
  }

  Future<void> _prefetchProducts() async {
    if (_hasPrefetchedProducts) return;
    _hasPrefetchedProducts = true;
    await getProducts([foreverProProductId]);
  }

  /// Fetch product details for the given product IDs
  Future<List<IAPProduct>> getProducts(List<String> productIds) async {
    try {
      debugPrint('IAP: Fetching products: $productIds');
      final ProductDetailsResponse response =
          await _inAppPurchase.queryProductDetails(productIds.toSet());

      if (response.error != null) {
        debugPrint('IAP Error: ${response.error?.message}');
        if (Platform.isIOS) {
          debugPrint('IAP iOS: Make sure products are configured in App Store Connect');
          debugPrint('IAP iOS: Product ID must match exactly: $productIds');
          debugPrint('IAP iOS: Signed agreement and banking info must be complete');
        }
        return [];
      }

      if (response.productDetails.isEmpty) {
        debugPrint('IAP: No products found for IDs: $productIds');
        debugPrint('IAP: notFound=${response.notFoundIDs}');
        if (Platform.isIOS) {
          debugPrint('IAP iOS: Verify product is "Ready to Submit" in App Store Connect');
          debugPrint('IAP iOS: Wait 2-24 hours after creating product for it to sync');
        }
        return [];
      }

      debugPrint('IAP: Found ${response.productDetails.length} product(s)');
      // Cache currency code from the first product for formatter usage
      final firstCurrency = response.productDetails.first.currencyCode;
      await _currencyPrefs.setCurrencyCode(firstCurrency);
      debugPrint("IAP: Store currency code set to: $firstCurrency");
      return response.productDetails
          .map((details) => IAPProduct.fromProductDetails(details))
          .toList();
    } catch (e) {
      debugPrint('IAP Exception: $e');
      if (Platform.isIOS) {
        debugPrint('IAP iOS Error: $e');
        debugPrint('IAP iOS: Check Console app for StoreKit errors');
      }
      return [];
    }
  }

  /// Get the Forever Pro product
  Future<IAPProduct?> getForeverProProduct() async {
    final products = await getProducts([foreverProProductId]);
    return products.isEmpty ? null : products.first;
  }

  /// Purchase a product
  Future<bool> purchaseProduct(IAPProduct product) async {
    try {
      if (product.rawProductDetails == null) {
        debugPrint('IAP: Product details not available for purchase');
        return false;
      }

      final PurchaseParam purchaseParam = PurchaseParam(
        productDetails: product.rawProductDetails!,
      );

      final result = await _inAppPurchase.buyNonConsumable(
        purchaseParam: purchaseParam,
      );

      debugPrint('IAP: Purchase initiated for ${product.id}, result: $result');
      return result;
    } catch (e) {
      debugPrint('IAP Purchase Exception: $e');
      return false;
    }
  }

  /// Restore previous purchases
  /// This queries the App Store (iOS) or Google Play (Android) for all non-consumable purchases
  /// For forever_pro (non-consumable), this will return the purchase if user has ever bought it
  /// This is called on app startup to sync with the store's source of truth
  Future<bool> restorePurchases() async {
    try {
      debugPrint('IAP: Querying store for non-consumable purchases...');
      _isRestoring = true;
      _foundProDuringRestore = false;
      await _inAppPurchase.restorePurchases();
      debugPrint('IAP: Restore purchases request completed');
      debugPrint('IAP: Any existing purchases will be processed via purchase stream');

      // Give the purchase stream a moment to process any restored purchases
      await Future.delayed(const Duration(milliseconds: 500));

      // If we were restoring and didn't find a forever_pro purchase,
      // clear the local pro status (store is the source of truth)
      if (_isRestoring && !_foundProDuringRestore) {
        debugPrint('IAP: No forever_pro purchase found during restore — clearing local pro status');
        final notPro = ProStatus.notPro();
        await _dbHelper.updateProStatus(notPro);
        _proStatusNotifier.value = notPro;
      }
      _isRestoring = false;

      return true;
    } catch (e) {
      _isRestoring = false;
      debugPrint('IAP Restore Exception: $e');
      return false;
    }
  }

  /// Handle purchase updates from the stream
  Future<void> _handlePurchaseUpdates(List<PurchaseDetails> purchaseDetailsList) async {
    if (purchaseDetailsList.isEmpty) {
      debugPrint('IAP: No purchases found in user account');
      return;
    }

    debugPrint('IAP: Processing ${purchaseDetailsList.length} purchase(s)');

    for (var purchaseDetails in purchaseDetailsList) {
      debugPrint('IAP: Purchase update - ${purchaseDetails.productID} '
          '(${purchaseDetails.status})');

      switch (purchaseDetails.status) {
        case PurchaseStatus.pending:
          debugPrint('IAP: Purchase pending for ${purchaseDetails.productID}');
          break;

        case PurchaseStatus.purchased:
          debugPrint('IAP: NEW purchase detected for ${purchaseDetails.productID}');
          await _handleSuccessfulPurchase(purchaseDetails);
          break;

        case PurchaseStatus.restored:
          debugPrint('IAP: RESTORED purchase from Google Play account for ${purchaseDetails.productID}');
          await _handleSuccessfulPurchase(purchaseDetails);
          break;

        case PurchaseStatus.canceled:
          debugPrint('IAP: Purchase canceled for ${purchaseDetails.productID}');
          if (!_isRestoring) {
            _purchaseCanceledNotifier.value++;
          }
          break;

        case PurchaseStatus.error:
          debugPrint('IAP: Purchase error - ${purchaseDetails.error}');
          if (!_isRestoring) {
            _purchaseCanceledNotifier.value++;
          }
          break;
      }

      // Complete purchase
      if (purchaseDetails.pendingCompletePurchase) {
        await _inAppPurchase.completePurchase(purchaseDetails);
      }
    }
  }

  /// Handle successful purchase
  Future<void> _handleSuccessfulPurchase(PurchaseDetails purchaseDetails) async {
    debugPrint('IAP: Purchase successful - ${purchaseDetails.productID}');

    // Parse transaction date
    // iOS: ISO 8601 date string (e.g., "2024-01-15T10:30:00Z")
    // Android: Unix timestamp in milliseconds as a string (e.g., "1705315800000")
    DateTime purchaseDateTime = DateTime.now();
    if (purchaseDetails.transactionDate != null) {
      try {
        debugPrint('IAP: Raw transaction date: ${purchaseDetails.transactionDate}');

        if (Platform.isAndroid) {
          // Android: Try parsing as milliseconds timestamp
          final timestamp = int.tryParse(purchaseDetails.transactionDate!);
          if (timestamp != null) {
            purchaseDateTime = DateTime.fromMillisecondsSinceEpoch(timestamp);
            debugPrint('IAP: Parsed Android transaction date from timestamp: $purchaseDateTime');
          }
        } else if (Platform.isIOS) {
          // iOS: Parse as ISO 8601 string
          purchaseDateTime = DateTime.parse(purchaseDetails.transactionDate!);
          debugPrint('IAP: Parsed iOS transaction date from ISO string: $purchaseDateTime');
        }
      } catch (e) {
        debugPrint('IAP: Failed to parse transaction date: $e, using current time');
        purchaseDateTime = DateTime.now();
      }
    }

    // Save purchase to database
    final purchase = PurchaseModel(
      productId: purchaseDetails.productID,
      purchaseId: purchaseDetails.purchaseID ?? '',
      purchaseDateTime: purchaseDateTime,
      isActive: true,
    );

    await _dbHelper.savePurchase(purchase);

    // Update pro status if this is the forever_pro product
    if (purchaseDetails.productID == foreverProProductId) {
      if (_isRestoring) {
        _foundProDuringRestore = true;
      }
      final proStatus = ProStatus.pro(
        productId: foreverProProductId,
        sinceDate: purchase.purchaseDateTime,
      );
      await _dbHelper.updateProStatus(proStatus);
      _proStatusNotifier.value = proStatus;
      debugPrint('IAP: User is now PRO!');
    }
  }

  /// Check if user is pro (syncs with database)
  Future<bool> isUserPro() async {
    final proStatus = await _dbHelper.getProStatus();
    _proStatusNotifier.value = proStatus;
    return proStatus.isPro;
  }

  /// Get current pro status
  Future<ProStatus> getProStatus() async {
    final proStatus = await _dbHelper.getProStatus();
    _proStatusNotifier.value = proStatus;
    return proStatus;
  }

  /// Get all purchases
  Future<List<PurchaseModel>> getAllPurchases() async {
    return _dbHelper.getAllPurchases();
  }

  /// Get active purchases
  Future<List<PurchaseModel>> getActivePurchases() async {
    return _dbHelper.getActivePurchases();
  }

  /// Dispose resources
  void dispose() {
    _purchaseStreamSubscription?.cancel();
    _proStatusNotifier.dispose();
  }
}
```

---

### 3.2 Product Models

#### **IAPProduct** (`lib/data/models/iap_product.dart`)

```dart
import 'package:equatable/equatable.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

class IAPProduct extends Equatable {
  final String id;
  final String title;
  final String description;
  final String price;
  final String rawPrice;
  final String? currencyCode;
  final ProductDetails? rawProductDetails;

  const IAPProduct({
    required this.id,
    required this.title,
    required this.description,
    required this.price,
    required this.rawPrice,
    this.currencyCode,
    this.rawProductDetails,
  });

  factory IAPProduct.fromProductDetails(ProductDetails details) {
    return IAPProduct(
      id: details.id,
      title: details.title,
      description: details.description,
      price: details.price,
      rawPrice: details.price, // Use price string as rawPrice
      currencyCode: details.currencyCode,
      rawProductDetails: details,
    );
  }

  @override
  List<Object?> get props => [id, title, description, price, rawPrice];

  IAPProduct copyWith({
    String? id,
    String? title,
    String? description,
    String? price,
    String? rawPrice,
    String? currencyCode,
    ProductDetails? rawProductDetails,
  }) {
    return IAPProduct(
      id: id ?? this.id,
      title: title ?? this.title,
      description: description ?? this.description,
      price: price ?? this.price,
      rawPrice: rawPrice ?? this.rawPrice,
      currencyCode: currencyCode ?? this.currencyCode,
      rawProductDetails: rawProductDetails ?? this.rawProductDetails,
    );
  }
}
```

---

#### **PurchaseModel** (`lib/data/models/purchase_model.dart`)

```dart
import 'package:equatable/equatable.dart';

class PurchaseModel extends Equatable {
  final String productId;
  final String purchaseId;
  final DateTime purchaseDateTime;
  final bool isActive;

  const PurchaseModel({
    required this.productId,
    required this.purchaseId,
    required this.purchaseDateTime,
    required this.isActive,
  });

  factory PurchaseModel.fromMap(Map<String, dynamic> map) {
    return PurchaseModel(
      productId: map['product_id'] as String,
      purchaseId: map['purchase_id'] as String,
      purchaseDateTime: DateTime.parse(map['purchase_date_time'] as String),
      isActive: (map['is_active'] as int) == 1,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'product_id': productId,
      'purchase_id': purchaseId,
      'purchase_date_time': purchaseDateTime.toIso8601String(),
      'is_active': isActive ? 1 : 0,
    };
  }

  @override
  List<Object?> get props => [productId, purchaseId, purchaseDateTime, isActive];

  PurchaseModel copyWith({
    String? productId,
    String? purchaseId,
    DateTime? purchaseDateTime,
    bool? isActive,
  }) {
    return PurchaseModel(
      productId: productId ?? this.productId,
      purchaseId: purchaseId ?? this.purchaseId,
      purchaseDateTime: purchaseDateTime ?? this.purchaseDateTime,
      isActive: isActive ?? this.isActive,
    );
  }
}
```

---

#### **ProStatus** (`lib/data/models/pro_status.dart`)

```dart
import 'package:equatable/equatable.dart';

class ProStatus extends Equatable {
  final bool isPro;
  final DateTime? proSinceDate;
  final String? activeProductId;

  const ProStatus({
    required this.isPro,
    this.proSinceDate,
    this.activeProductId,
  });

  factory ProStatus.notPro() {
    return const ProStatus(isPro: false);
  }

  factory ProStatus.pro({
    required String productId,
    required DateTime sinceDate,
  }) {
    return ProStatus(
      isPro: true,
      proSinceDate: sinceDate,
      activeProductId: productId,
    );
  }

  factory ProStatus.fromMap(Map<String, dynamic> map) {
    return ProStatus(
      isPro: (map['is_pro'] as int) == 1,
      proSinceDate:
          map['pro_since_date'] != null ? DateTime.parse(map['pro_since_date'] as String) : null,
      activeProductId: map['active_product_id'] as String?,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'is_pro': isPro ? 1 : 0,
      'pro_since_date': proSinceDate?.toIso8601String(),
      'active_product_id': activeProductId,
    };
  }

  @override
  List<Object?> get props => [isPro, proSinceDate, activeProductId];

  ProStatus copyWith({
    bool? isPro,
    DateTime? proSinceDate,
    String? activeProductId,
  }) {
    return ProStatus(
      isPro: isPro ?? this.isPro,
      proSinceDate: proSinceDate ?? this.proSinceDate,
      activeProductId: activeProductId ?? this.activeProductId,
    );
  }
}
```

---

#### **Models Export** (`lib/data/models/models.dart`)

```dart
export 'tape_entry.dart';
export 'calculation_session.dart';
export 'iap_product.dart';
export 'purchase_model.dart';
export 'pro_status.dart';
```

---

### 3.3 IAP Constants (`lib/utils/iap_constants.dart`)

```dart
/// IAP Product IDs and Configuration
class IAPConstants {
  // Product IDs - must match Google Play Console and App Store Connect
  static const String foreverProProductId = 'forever_pro';

  // List of all in-app purchasable products
  static const List<String> allProductIds = [
    foreverProProductId,
  ];

  // Product names for display
  static const Map<String, String> productNames = {
    foreverProProductId: 'Pro (Forever)',
  };

  // Product descriptions for display
  static const Map<String, String> productDescriptions = {
    foreverProProductId: 'Unlock all premium features forever',
  };
}
```

---

### 3.4 IAP Helper Functions (`lib/utils/iap_helpers.dart`)

```dart
import '../bloc/iap/iap_state.dart';

/// Helper function to extract pro status from any IAP state
bool getProStatusFromState(IAPState state) {
  if (state is IAPReady) {
    return state.proStatus.isPro;
  } else if (state is ProductsLoaded) {
    return state.proStatus.isPro;
  }
  return false;
}
```

---

## 4. BLoC/State Management

### 4.1 IAPBloc (`lib/bloc/iap/iap_bloc.dart`)

```dart
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../services/iap_manager.dart';
import 'iap_event.dart';
import 'iap_state.dart';

class IAPBloc extends Bloc<IAPEvent, IAPState> {
  final IAPManager _iapManager;

  IAPBloc({IAPManager? iapManager})
      : _iapManager = iapManager ?? IAPManager(),
        super(const IAPInitial()) {
    on<IAPInitialize>(_onInitialize);
    on<FetchProducts>(_onFetchProducts);
    on<PurchaseProduct>(_onPurchaseProduct);
    on<RestorePurchases>(_onRestorePurchases);
    on<PurchaseCanceled>(_onPurchaseCanceled);
    on<RefreshProStatus>(_onRefreshProStatus);

    // Listen to IAP manager's pro status changes (fired by purchase stream)
    _iapManager.proStatusNotifier.addListener(_onProStatusChanged);
    // Listen to purchase cancellations/errors from the purchase stream
    _iapManager.purchaseCanceledNotifier.addListener(_onPurchaseCanceled_);
  }

  /// Called when IAP manager's pro status changes (purchase stream processed a purchase)
  void _onProStatusChanged() {
    add(const RefreshProStatus());
  }

  /// Called when a purchase is canceled or errors out via the purchase stream
  void _onPurchaseCanceled_() {
    add(const PurchaseCanceled());
  }

  /// Handle IAP initialization
  Future<void> _onInitialize(IAPInitialize event, Emitter<IAPState> emit) async {
    try {
      emit(const IAPInitializing());
      await _iapManager.initialize();
      final proStatus = await _iapManager.getProStatus();
      emit(IAPReady(proStatus: proStatus));
    } catch (e) {
      emit(IAPError(message: 'Failed to initialize IAP: $e'));
    }
  }

  /// Handle fetching products
  Future<void> _onFetchProducts(FetchProducts event, Emitter<IAPState> emit) async {
    try {
      final proStatus = await _iapManager.getProStatus();
      final products = await _iapManager.getProducts(event.productIds);
      emit(ProductsLoaded(products: products, proStatus: proStatus));
    } catch (e) {
      emit(IAPError(message: 'Failed to fetch products: $e'));
    }
  }

  /// Handle product purchase — only initiates the purchase flow.
  /// The actual success/failure comes through the purchase stream
  /// which triggers _onProStatusChanged -> RefreshProStatus.
  Future<void> _onPurchaseProduct(PurchaseProduct event, Emitter<IAPState> emit) async {
    try {
      final currentState = state;
      if (currentState is! ProductsLoaded) return;

      // Show purchasing state (keeps products visible)
      emit(currentState.copyWith(purchaseFlowStatus: PurchaseFlowStatus.purchasing));

      final product = await _iapManager.getForeverProProduct();
      if (product == null) {
        emit(currentState.copyWith(
          purchaseFlowStatus: PurchaseFlowStatus.purchaseError,
          errorMessage: 'Product not found',
        ));
        return;
      }

      final initiated = await _iapManager.purchaseProduct(product);

      if (!initiated) {
        // Purchase was not even initiated (e.g. already owned, or store error)
        final proStatus = await _iapManager.getProStatus();
        if (proStatus.isPro) {
          // Already owned — treat as success
          emit(currentState.copyWith(
            proStatus: proStatus,
            purchaseFlowStatus: PurchaseFlowStatus.purchaseSuccess,
          ));
        } else {
          emit(currentState.copyWith(
            purchaseFlowStatus: PurchaseFlowStatus.purchaseError,
            errorMessage: 'Purchase could not be initiated',
          ));
        }
        return;
      }

      // Purchase was initiated successfully.
      // Now we wait — the purchase stream will fire _onProStatusChanged
      // which will trigger RefreshProStatus and update the state.
      // The UI stays in "purchasing" state until the stream fires.
    } catch (e) {
      final currentState = state;
      if (currentState is ProductsLoaded) {
        emit(currentState.copyWith(
          purchaseFlowStatus: PurchaseFlowStatus.purchaseError,
          errorMessage: 'Purchase error: $e',
        ));
      }
    }
  }

  /// Handle restoring purchases
  Future<void> _onRestorePurchases(RestorePurchases event, Emitter<IAPState> emit) async {
    try {
      final currentState = state;
      if (currentState is ProductsLoaded) {
        emit(currentState.copyWith(purchaseFlowStatus: PurchaseFlowStatus.restoring));
      }

      // restorePurchases() in the manager waits for the purchase stream
      // and clears pro status if no purchases found, so we just read the result.
      final success = await _iapManager.restorePurchases();

      if (!success) {
        if (currentState is ProductsLoaded) {
          emit(currentState.copyWith(
            purchaseFlowStatus: PurchaseFlowStatus.purchaseError,
            errorMessage: 'Failed to restore purchases',
          ));
        }
        return;
      }

      final updatedProStatus = await _iapManager.getProStatus();
      if (currentState is ProductsLoaded) {
        emit(currentState.copyWith(
          proStatus: updatedProStatus,
          purchaseFlowStatus: updatedProStatus.isPro
              ? PurchaseFlowStatus.restoreSuccess
              : PurchaseFlowStatus.restoreNoPurchases,
        ));
      }
    } catch (e) {
      final currentState = state;
      if (currentState is ProductsLoaded) {
        emit(currentState.copyWith(
          purchaseFlowStatus: PurchaseFlowStatus.purchaseError,
          errorMessage: 'Restore purchases error: $e',
        ));
      }
    }
  }

  /// Handle purchase canceled/error from the purchase stream.
  /// This resets the dialog from "purchasing" back to "idle" so the user
  /// can try again or close the dialog.
  Future<void> _onPurchaseCanceled(PurchaseCanceled event, Emitter<IAPState> emit) async {
    final currentState = state;
    if (currentState is ProductsLoaded &&
        currentState.purchaseFlowStatus == PurchaseFlowStatus.purchasing) {
      emit(currentState.copyWith(
        purchaseFlowStatus: PurchaseFlowStatus.idle,
      ));
    }
  }

  /// Handle refreshing pro status — called when the purchase stream processes a purchase.
  /// This is the key handler that detects purchase success.
  Future<void> _onRefreshProStatus(RefreshProStatus event, Emitter<IAPState> emit) async {
    try {
      final proStatus = await _iapManager.getProStatus();
      final currentState = state;

      if (currentState is ProductsLoaded) {
        // If we were in "purchasing" and pro status just became true, that's a success!
        final wasWaitingForPurchase =
            currentState.purchaseFlowStatus == PurchaseFlowStatus.purchasing;
        final justBecamePro = proStatus.isPro && !currentState.proStatus.isPro;

        if (wasWaitingForPurchase && justBecamePro) {
          emit(currentState.copyWith(
            proStatus: proStatus,
            purchaseFlowStatus: PurchaseFlowStatus.purchaseSuccess,
          ));
        } else {
          // Just update pro status, keep current flow status
          emit(currentState.copyWith(proStatus: proStatus));
        }
      } else if (currentState is IAPReady) {
        emit(IAPReady(proStatus: proStatus));
      } else {
        emit(IAPReady(proStatus: proStatus));
      }
    } catch (e) {
      // Silently fail — this is a background refresh
    }
  }

  @override
  Future<void> close() {
    _iapManager.proStatusNotifier.removeListener(_onProStatusChanged);
    _iapManager.purchaseCanceledNotifier.removeListener(_onPurchaseCanceled_);
    _iapManager.dispose();
    return super.close();
  }
}
```

---

### 4.2 IAPEvent (`lib/bloc/iap/iap_event.dart`)

```dart
import 'package:equatable/equatable.dart';

abstract class IAPEvent extends Equatable {
  const IAPEvent();

  @override
  List<Object?> get props => [];
}

class IAPInitialize extends IAPEvent {
  const IAPInitialize();
}

class FetchProducts extends IAPEvent {
  final List<String> productIds;

  const FetchProducts(this.productIds);

  @override
  List<Object?> get props => [productIds];
}

class PurchaseProduct extends IAPEvent {
  final String productId;

  const PurchaseProduct(this.productId);

  @override
  List<Object?> get props => [productId];
}

class RestorePurchases extends IAPEvent {
  const RestorePurchases();
}

class PurchaseCanceled extends IAPEvent {
  const PurchaseCanceled();
}

class RefreshProStatus extends IAPEvent {
  const RefreshProStatus();
}
```

---

### 4.3 IAPState (`lib/bloc/iap/iap_state.dart`)

```dart
import 'package:equatable/equatable.dart';
import '../../data/models/models.dart';

abstract class IAPState extends Equatable {
  const IAPState();

  @override
  List<Object?> get props => [];
}

class IAPInitial extends IAPState {
  const IAPInitial();
}

class IAPInitializing extends IAPState {
  const IAPInitializing();
}

class IAPReady extends IAPState {
  final ProStatus proStatus;

  const IAPReady({required this.proStatus});

  @override
  List<Object?> get props => [proStatus];
}

/// Main state for the purchase dialog.
/// Holds products + proStatus and optional transient purchase status.
class ProductsLoaded extends IAPState {
  final List<IAPProduct> products;
  final ProStatus proStatus;
  final PurchaseFlowStatus purchaseFlowStatus;
  final String? errorMessage;

  const ProductsLoaded({
    required this.products,
    required this.proStatus,
    this.purchaseFlowStatus = PurchaseFlowStatus.idle,
    this.errorMessage,
  });

  @override
  List<Object?> get props => [products, proStatus, purchaseFlowStatus, errorMessage];

  ProductsLoaded copyWith({
    List<IAPProduct>? products,
    ProStatus? proStatus,
    PurchaseFlowStatus? purchaseFlowStatus,
    String? errorMessage,
  }) {
    return ProductsLoaded(
      products: products ?? this.products,
      proStatus: proStatus ?? this.proStatus,
      purchaseFlowStatus: purchaseFlowStatus ?? this.purchaseFlowStatus,
      errorMessage: errorMessage,
    );
  }
}

/// Status of the purchase/restore flow within ProductsLoaded state.
enum PurchaseFlowStatus {
  idle,
  purchasing,
  restoring,
  purchaseSuccess,
  purchaseError,
  restoreSuccess,
  restoreNoPurchases,
}

class IAPError extends IAPState {
  final String message;

  const IAPError({required this.message});

  @override
  List<Object?> get props => [message];
}
```

---

## 5. UI Components & Widgets

### 5.1 IAPExampleWidget (`lib/ui/widgets/iap_example_widget.dart`)

This is a complete reference implementation showing how to use the IAP system in your UI.

```dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:your_app/bloc/iap/iap_bloc.dart';
import 'package:your_app/bloc/iap/iap_event.dart';
import 'package:your_app/bloc/iap/iap_state.dart';
import 'package:your_app/utils/iap_helpers.dart';

/// Example widget showing how to use the IAP system
/// This is a reference implementation - adapt to your UI needs
class IAPExampleWidget extends StatefulWidget {
  const IAPExampleWidget({super.key});

  @override
  State<IAPExampleWidget> createState() => _IAPExampleWidgetState();
}

class _IAPExampleWidgetState extends State<IAPExampleWidget> {
  @override
  void initState() {
    super.initState();
    // Fetch products when widget is built
    _fetchProducts();
  }

  void _fetchProducts() {
    context.read<IAPBloc>().add(const FetchProducts(['forever_pro']));
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<IAPBloc, IAPState>(
      listenWhen: (previous, current) {
        if (current is! ProductsLoaded || previous is! ProductsLoaded) {
          return false;
        }
        return previous.purchaseFlowStatus != current.purchaseFlowStatus;
      },
      listener: (context, state) {
        if (state is! ProductsLoaded) return;

        if (state.purchaseFlowStatus == PurchaseFlowStatus.purchaseSuccess) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Purchase successful! You are now PRO!'),
              backgroundColor: Colors.green,
              duration: Duration(seconds: 3),
            ),
          );
        } else if (state.purchaseFlowStatus == PurchaseFlowStatus.purchaseError) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Purchase failed: ${state.errorMessage ?? ''}'),
              backgroundColor: Colors.red,
              duration: const Duration(seconds: 3),
            ),
          );
        }
      },
      child: BlocBuilder<IAPBloc, IAPState>(
        builder: (context, state) {
          return Scaffold(
            appBar: AppBar(
              title: const Text('Pro Upgrade'),
              centerTitle: true,
            ),
            body: Center(
              child: _buildContent(context, state),
            ),
          );
        },
      ),
    );
  }

  Widget _buildContent(BuildContext context, IAPState state) {
    if (state is IAPInitializing) {
      return const CircularProgressIndicator();
    }

    if (state is ProductsLoaded) {
      return _buildProductsList(context, state);
    }

    if (state is IAPError) {
      return Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.error_outline, size: 48, color: Colors.red),
          const SizedBox(height: 16),
          Text(
            state.message,
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.red),
          ),
          const SizedBox(height: 16),
          ElevatedButton(
            onPressed: _fetchProducts,
            child: const Text('Retry'),
          ),
        ],
      );
    }

    if (state is IAPReady) {
      if (state.proStatus.isPro) {
        return Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.verified, size: 64, color: Colors.green),
            const SizedBox(height: 16),
            const Text(
              'You are a PRO user!',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              'Pro since ${state.proStatus.proSinceDate?.toString().split(' ')[0]}',
              style: const TextStyle(color: Colors.grey),
            ),
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: () {
                context.read<IAPBloc>().add(const RestorePurchases());
              },
              child: const Text('Restore Purchases'),
            ),
          ],
        );
      } else {
        return Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text('Loading products...'),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _fetchProducts,
              child: const Text('Fetch Products'),
            ),
          ],
        );
      }
    }

    return const Text('Unknown state');
  }

  Widget _buildProductsList(BuildContext context, ProductsLoaded state) {
    if (state.products.isEmpty) {
      return Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.shopping_bag_outlined, size: 48),
          const SizedBox(height: 16),
          const Text('No products available'),
          const SizedBox(height: 24),
          ElevatedButton(
            onPressed: () {
              context.read<IAPBloc>().add(const RestorePurchases());
            },
            child: const Text('Restore Purchases'),
          ),
        ],
      );
    }

    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: ListView.builder(
        itemCount: state.products.length,
        itemBuilder: (context, index) {
          final product = state.products[index];
          return Card(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    product.title,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    product.description,
                    style: const TextStyle(color: Colors.grey),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        product.price,
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          color: Colors.green,
                        ),
                      ),
                      ElevatedButton(
                        onPressed: state.proStatus.isPro
                            ? null
                            : () {
                                context.read<IAPBloc>().add(
                                  PurchaseProduct(product.id),
                                );
                              },
                        child: Text(state.proStatus.isPro ? 'Owned' : 'Buy Now'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

/// Simpler widget that just shows if user is pro
class ProStatusWidget extends StatelessWidget {
  const ProStatusWidget({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<IAPBloc, IAPState>(
      builder: (context, state) {
        final isPro = getProStatusFromState(state);

        return Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: isPro ? Colors.green : Colors.grey,
            borderRadius: BorderRadius.circular(4),
          ),
          child: Text(
            isPro ? 'PRO ✓' : 'FREE',
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.bold,
            ),
          ),
        );
      },
    );
  }
}
```

---

## 6. Theme/Styling Configuration

### 6.1 AppTheme (`lib/ui/theme/app_theme.dart`)

Define color schemes and theme settings:

```dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Semantic color palette that resolves per light/dark mode.
class AppColors {
  final Color primaryPurple;
  final Color primaryPurpleLight;
  final Color accentGreen;

  final Color background;
  final Color surface;
  final Color textPrimary;
  final Color textSecondary;
  final Color textTertiary;
  final Color border;

  final Color negative;
  final Color positive;

  final Color keypadBackground;
  final Color keyDefault;
  final Color keyOperator;
  final Color keyAction;

  final Color chipBackground;

  const AppColors({
    required this.primaryPurple,
    required this.primaryPurpleLight,
    required this.accentGreen,
    required this.background,
    required this.surface,
    required this.textPrimary,
    required this.textSecondary,
    required this.textTertiary,
    required this.border,
    required this.negative,
    required this.positive,
    required this.keypadBackground,
    required this.keyDefault,
    required this.keyOperator,
    required this.keyAction,
    required this.chipBackground,
  });

  static const AppColors light = AppColors(
    primaryPurple: Color(0xFF7C3AED),
    primaryPurpleLight: Color(0xFFA78BFA),
    accentGreen: Color(0xFF10B981),
    background: Color(0xFFF8FAFC),
    surface: Colors.white,
    textPrimary: Color(0xFF1E293B),
    textSecondary: Color(0xFF64748B),
    textTertiary: Color(0xFF94A3B8),
    border: Color(0xFFE2E8F0),
    negative: Color(0xFFEF4444),
    positive: Color(0xFF10B981),
    keypadBackground: Color(0xFFF1F5F9),
    keyDefault: Colors.white,
    keyOperator: Color(0xFFEDE9FE),
    keyAction: Color(0xFF7C3AED),
    chipBackground: Color(0xFFE0E0E0),
  );

  static const AppColors dark = AppColors(
    primaryPurple: Color(0xFF9F67FF),
    primaryPurpleLight: Color(0xFFB794F6),
    accentGreen: Color(0xFF34D399),
    background: Color(0xFF0F172A),
    surface: Color(0xFF1E293B),
    textPrimary: Color(0xFFF1F5F9),
    textSecondary: Color(0xFF94A3B8),
    textTertiary: Color(0xFF64748B),
    border: Color(0xFF334155),
    negative: Color(0xFFF87171),
    positive: Color(0xFF34D399),
    keypadBackground: Color(0xFF1E293B),
    keyDefault: Color(0xFF334155),
    keyOperator: Color(0xFF2E1065),
    keyAction: Color(0xFF7C3AED),
    chipBackground: Color(0xFF475569),
  );
}

/// Resolve [AppColors] from the current theme brightness.
extension AppColorsExtension on BuildContext {
  AppColors get colors {
    final brightness = Theme.of(this).brightness;
    return brightness == Brightness.dark ? AppColors.dark : AppColors.light;
  }

  bool get isDark => Theme.of(this).brightness == Brightness.dark;
}

class AppTheme {
  // Keep brand constants for places that are brightness-independent
  // (e.g. the PRO button is always green, error snackbar always red).
  static const Color primaryPurple = Color(0xFF7C3AED);
  static const Color accentGreen = Color(0xFF10B981);
  static const Color negative = Color(0xFFEF4444);

  static ThemeData get lightTheme {
    const c = AppColors.light;
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: ColorScheme.fromSeed(
        seedColor: c.primaryPurple,
        brightness: Brightness.light,
        primary: c.primaryPurple,
        secondary: c.accentGreen,
        surface: c.surface,
      ),
      scaffoldBackgroundColor: c.background,
      fontFamily: 'Roboto',
      appBarTheme: AppBarTheme(
        backgroundColor: c.surface,
        foregroundColor: c.textPrimary,
        elevation: 0,
        centerTitle: false,
        systemOverlayStyle: const SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: Brightness.dark,
          statusBarBrightness: Brightness.light,
          systemNavigationBarColor: Colors.white,
          systemNavigationBarIconBrightness: Brightness.dark,
        ),
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: c.primaryPurple,
        foregroundColor: Colors.white,
      ),
      cardTheme: CardThemeData(
        color: c.surface,
        elevation: 0,
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: c.surface,
      ),
      snackBarTheme: const SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: c.keypadBackground,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 12,
        ),
      ),
    );
  }

  static ThemeData get darkTheme {
    const c = AppColors.dark;
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: ColorScheme.fromSeed(
        seedColor: c.primaryPurple,
        brightness: Brightness.dark,
        primary: c.primaryPurple,
        secondary: c.accentGreen,
        surface: c.surface,
      ),
      scaffoldBackgroundColor: c.background,
      fontFamily: 'Roboto',
      appBarTheme: AppBarTheme(
        backgroundColor: c.surface,
        foregroundColor: c.textPrimary,
        elevation: 0,
        centerTitle: false,
        systemOverlayStyle: const SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: Brightness.light,
          statusBarBrightness: Brightness.dark,
          systemNavigationBarColor: Color(0xFF0F172A),
          systemNavigationBarIconBrightness: Brightness.light,
        ),
      ),
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: c.primaryPurple,
        foregroundColor: Colors.white,
      ),
      cardTheme: CardThemeData(
        color: c.surface,
        elevation: 0,
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: c.surface,
      ),
      snackBarTheme: const SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: c.keypadBackground,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 12,
        ),
      ),
    );
  }
}

class AppSpacing {
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 16;
  static const double lg = 24;
  static const double xl = 32;
  static const double xxl = 48;
}

class AppRadius {
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 24;
}
```

---

## 7. Database Configuration

### 7.1 Database Schema (in DatabaseHelper)

Add these methods to your existing `DatabaseHelper`:

```dart
// Purchase operations
Future<void> savePurchase(PurchaseModel purchase) async {
  final db = await database;
  await db.insert(
    'purchases',
    {
      'product_id': purchase.productId,
      'purchase_id': purchase.purchaseId,
      'purchase_date_time': purchase.purchaseDateTime.toIso8601String(),
      'is_active': purchase.isActive ? 1 : 0,
    },
    conflictAlgorithm: ConflictAlgorithm.replace,
  );
}

Future<List<PurchaseModel>> getAllPurchases() async {
  final db = await database;
  final maps = await db.query('purchases');
  return maps.map((m) => PurchaseModel.fromMap(m)).toList();
}

Future<List<PurchaseModel>> getActivePurchases() async {
  final db = await database;
  final maps = await db.query(
    'purchases',
    where: 'is_active = ?',
    whereArgs: [1],
  );
  return maps.map((m) => PurchaseModel.fromMap(m)).toList();
}

Future<PurchaseModel?> getPurchaseByProductId(String productId) async {
  final db = await database;
  final maps = await db.query(
    'purchases',
    where: 'product_id = ? AND is_active = ?',
    whereArgs: [productId, 1],
  );
  if (maps.isEmpty) return null;
  return PurchaseModel.fromMap(maps.first);
}

// Pro status operations
Future<ProStatus> getProStatus() async {
  final db = await database;
  final maps = await db.query('user_pro_status');
  if (maps.isEmpty) {
    // If no record, create default
    final now = DateTime.now().toIso8601String();
    await db.insert('user_pro_status', {
      'id': 1,
      'is_pro': 0,
      'pro_since_date': null,
      'active_product_id': null,
      'last_updated': now,
    });
    return ProStatus.notPro();
  }
  return ProStatus.fromMap(maps.first);
}

Future<void> updateProStatus(ProStatus proStatus) async {
  final db = await database;
  await db.update(
    'user_pro_status',
    {
      ...proStatus.toMap(),
      'last_updated': DateTime.now().toIso8601String(),
    },
    where: 'id = ?',
    whereArgs: [1],
  );
}
```

Add these to your database schema creation:

```dart
// In _onCreate():
await db.execute('''
  CREATE TABLE purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL,
    purchase_id TEXT NOT NULL UNIQUE,
    purchase_date_time TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1
  )
''');

await db.execute('''
  CREATE TABLE user_pro_status (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    is_pro INTEGER NOT NULL DEFAULT 0,
    pro_since_date TEXT,
    active_product_id TEXT,
    last_updated TEXT NOT NULL
  )
''');

// Insert initial pro status
final now = DateTime.now().toIso8601String();
await db.execute('''
  INSERT INTO user_pro_status (id, is_pro, pro_since_date, active_product_id, last_updated) 
  VALUES (1, 0, NULL, NULL, '$now')
''');
```

---

## 8. App Initialization

### 8.1 main.dart

```dart
import 'package:your_app/services/currency_preferences.dart';
import 'package:your_app/services/theme_preferences.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'l10n/app_localizations.dart';
import 'bloc/sessions/sessions_bloc.dart';
import 'bloc/iap/iap_bloc.dart';
import 'bloc/iap/iap_event.dart';
import 'ui/screens/sessions_screen.dart';
import 'ui/theme/app_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize preferences before running the app
  await CurrencyPreferences().initialize();
  await ThemePreferences().initialize();

  runApp(const YourAppName());
}

class YourAppName extends StatefulWidget {
  const YourAppName({super.key});

  @override
  State<YourAppName> createState() => _YourAppNameState();
}

class _YourAppNameState extends State<YourAppName> {
  final CurrencyPreferences _currencyPrefs = CurrencyPreferences();
  final ThemePreferences _themePrefs = ThemePreferences();

  @override
  void initState() {
    super.initState();
    _currencyPrefs.currencyChangeNotifier.addListener(_rebuild);
    _themePrefs.themeChangeNotifier.addListener(_rebuild);
  }

  @override
  void dispose() {
    _currencyPrefs.currencyChangeNotifier.removeListener(_rebuild);
    _themePrefs.themeChangeNotifier.removeListener(_rebuild);
    super.dispose();
  }

  void _rebuild() {
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    return MultiBlocProvider(
      providers: [
        BlocProvider(
          create: (_) => YourSessionsBloc(),
        ),
        BlocProvider(
          create: (_) => IAPBloc()..add(const IAPInitialize()),  // ← Initialize IAP here
        ),
      ],
      child: MaterialApp(
        title: 'Your App',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        themeMode: _themePrefs.themeMode,
        localizationsDelegates: const [
          AppLocalizations.delegate,
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        supportedLocales: const [
          Locale('en'),
        ],
        home: const YourHomeScreen(),
      ),
    );
  }
}
```

---

## 9. Purchase Flow Diagram

```
APP STARTUP
    ↓
main.dart creates IAPBloc with IAPInitialize event
    ↓
IAPBloc._onInitialize()
    ↓
IAPManager.initialize():
  1. Load cached pro status from database
  2. Check if IAP is available on device
  3. Listen to purchase stream
  4. Prefetch products (caches store currency)
  5. Restore purchases from store (source of truth)
    ↓
Purchase Stream listens for updates
    ↓
User taps "Buy Now"
    ↓
IAPBloc.PurchaseProduct event
    ↓
IAPManager.purchaseProduct(product)
    ↓
Purchase sheet appears (native platform UI)
    ↓
User completes/cancels purchase
    ↓
Purchase stream receives update
    ↓
IAPManager._handlePurchaseUpdates():
  - Parses transaction date (iOS: ISO8601, Android: milliseconds)
  - Saves purchase to database
  - Updates pro status in database
  - Notifies proStatusNotifier
    ↓
IAPBloc listens to proStatusNotifier
    ↓
IAPBloc.RefreshProStatus event
    ↓
IAPBloc._onRefreshProStatus() emits ProductsLoaded with updated proStatus
    ↓
UI responds to state change (shows success/error)
```

---

## 10. Key Implementation Details

### 10.1 Cross-Platform Transaction Date Parsing

The purchase timestamp comes in different formats on iOS and Android:

```dart
DateTime purchaseDateTime = DateTime.now();
if (purchaseDetails.transactionDate != null) {
  try {
    debugPrint('IAP: Raw transaction date: ${purchaseDetails.transactionDate}');

    if (Platform.isAndroid) {
      // Android: Unix milliseconds as string (e.g., "1705315800000")
      final timestamp = int.tryParse(purchaseDetails.transactionDate!);
      if (timestamp != null) {
        purchaseDateTime = DateTime.fromMillisecondsSinceEpoch(timestamp);
        debugPrint('IAP: Parsed Android transaction date: $purchaseDateTime');
      }
    } else if (Platform.isIOS) {
      // iOS: ISO 8601 string (e.g., "2024-01-15T10:30:00Z")
      purchaseDateTime = DateTime.parse(purchaseDetails.transactionDate!);
      debugPrint('IAP: Parsed iOS transaction date: $purchaseDateTime');
    }
  } catch (e) {
    debugPrint('IAP: Failed to parse transaction date: $e, using current time');
    purchaseDateTime = DateTime.now();
  }
}
```

### 10.2 Store as Source of Truth

The implementation treats the App Store/Google Play as the **source of truth** for purchases:

1. **On app startup**, `restorePurchases()` queries the store
2. **If user has purchased** but local DB doesn't have it → restore syncs it
3. **If local DB has pro status** but store doesn't → restore clears local status
4. This prevents users from downgrading their account locally

### 10.3 ValueNotifiers for Background Updates

The `IAPManager` uses `ValueNotifier`s to notify the BLoC of purchase stream updates:

```dart
// Fired when purchase succeeds
_proStatusNotifier = ValueNotifier<ProStatus>(ProStatus.notPro());

// Fired when purchase fails/is canceled
_purchaseCanceledNotifier = ValueNotifier<int>(0);
```

The BLoC listens to these and converts notifier changes into events:

```dart
_iapManager.proStatusNotifier.addListener(_onProStatusChanged);
_iapManager.purchaseCanceledNotifier.addListener(_onPurchaseCanceled_);
```

### 10.4 Non-Consumable Purchase

The implementation uses **non-consumable** purchases (`buyNonConsumable`):
- One-time purchase with no expiry
- Automatically restored across devices
- Store automatically handles restoration

---

## 11. Important Configuration

### 11.1 Product ID Setup

The product ID **'forever_pro'** must match exactly in:

1. **App Store Connect** (iOS):
   - App → In-App Purchases → Create New
   - Reference Name: "Forever Pro"
   - Product ID: **forever_pro** (exact match!)
   - Product Type: Non-Consumable
   - Status: "Ready to Submit"

2. **Google Play Console** (Android):
   - Products → In-App Products → Create New
   - Product ID: **forever_pro** (exact match!)
   - Title: "Forever Pro"
   - Status: Published

3. **Your Code**:
   ```dart
   // iap_manager.dart (line 10)
   const String foreverProProductId = 'forever_pro';
   
   // iap_constants.dart (line 4)
   static const String foreverProProductId = 'forever_pro';
   ```

### 11.2 Testing on iOS

**Requirements:**
- App Store Connect account with signed agreement
- Sandbox Apple ID (created in App Store Connect)
- TestFlight build deployed
- Use Sandbox Apple ID to test purchases

**Product States:**
- "Ready to Submit" - Required for testing and App Store
- "Waiting for Upload" - Not ready yet
- "Removed from Sale" - Product won't show

### 11.3 Platform Configuration

#### Android

**AndroidManifest.xml Configuration:**

Add the following permission to `android/app/src/main/AndroidManifest.xml`:

```xml
<uses-permission android:name="com.android.vending.BILLING" />
```

**Location:** Add this line with other permissions, before the `<application>` tag.

**Why:** 
- Required by Google Play Billing Library
- Grants app permission to initiate purchases
- Mandatory for any in-app purchase functionality on Android
- Google Play will reject APK without this permission

**Example:**
```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="com.android.vending.BILLING" />
    
    <application>
        ...
    </application>
</manifest>
```

#### iOS

Use local StoreKit configuration for testing before products are live in App Store Connect.

**StoreKit local testing setup (Debug):**

1. Create `ios/Runner/Configuration.storekit` and add your non-consumable product:
   - Product ID: `forever_pro_artquest`
   - Type: `NonConsumable`
2. Open `Runner.xcodeproj` in Xcode and make sure `Configuration.storekit` is visible under the `Runner` group.
3. Attach it to the Debug scheme:
   - Runner scheme -> Edit Scheme -> Run -> Options
   - StoreKit Configuration -> `Runner/Configuration.storekit`
4. Run from Xcode (Debug) and test purchases locally without App Store Connect products.

**Important notes:**
- Local StoreKit testing works only when launched from Xcode with the configured scheme.
- For TestFlight/production-like flow, use real products in App Store Connect and sandbox accounts.

**If the "In-App Purchase" capability doesn't appear in Xcode, create `ios/Runner/Runner.entitlements`:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.developer.in-app-purchase</key>
    <true/>
</dict>
</plist>
```

Then in Xcode: Runner → Build Settings → Code Sign Entitlements → Set to `Runner/Runner.entitlements`

---

### 11.5 Debug Pro Testing Controls (Flutter)

In debug builds only, Settings includes a **Development** section with actions to simulate purchase state:

- **Grant Test Pro Access** -> sets local Pro status to true.
- **Revoke Test Pro Access** -> clears local Pro status.

Implementation notes:
- Controls are gated by `kDebugMode`, so they are hidden in release builds.
- Manual debug state uses a dedicated product id marker (`debug_manual_pro`) in local DB.
- During restore, debug manual Pro is preserved in debug builds to avoid immediate reset when no live products exist.

Recommended usage:
1. Build and run a debug build.
2. Open Settings -> Development.
3. Use Grant/Revoke buttons to verify all Pro/Free UI gates.
4. Once live products are available, validate with real purchase and restore flow.

---

### 11.4 Testing on Android

**Requirements:**
- Signed APK with release keystore
- Google Play Console account
- Test account added to testers list

**Product Status:**
- Can be in Draft or Published
- Test account must be added in Settings → License Testing

---

## 12. Error Handling & Debugging

### 12.1 Common Issues

**No products found on iOS:**
```
✓ Check: App Store Connect → Products → "Ready to Submit" status
✓ Check: Product ID matches exactly (case-sensitive)
✓ Wait: 2-24 hours for sync with App Store
✓ Check: App Store Connect agreement is signed
✓ Check: Banking info is complete
```

**Purchase stream not firing:**
```
✓ Check: IAP availability on device
✓ Check: Test account added to Google Play Console (Android)
✓ Check: Using Sandbox Apple ID (iOS)
✓ Check: Build is signed with correct keystore (Android)
```

**Transaction date parsing fails:**
```
→ Fallback to DateTime.now() (see code)
→ Check device timezone settings
→ Enable debug logs to see raw transaction dates
```

**App crashes during initialization:**
```dart
// SafetyCheck: IAP may not be available in debug mode on simulator
if (!available && Platform.isIOS && !kReleaseMode) {
  // OK on iOS simulator in debug mode
  debugPrint('IAP: Running on simulator - expected behavior');
}
```

### 12.2 Debug Logging

Enable debug output to see all IAP operations:

```
flutter run -v | grep "IAP:"
```

Key debug messages:
- `IAP: Initializing for...` - Initialization started
- `IAP: In-app purchase is available` - IAP available
- `IAP: Found X product(s)` - Products loaded
- `IAP: NEW purchase detected` - Purchase successful
- `IAP: User is now PRO!` - Status updated
- `IAP: No forever_pro purchase found` - Restore sync

---

## 13. Testing Checklist

- [ ] All dependencies added to pubspec.yaml
- [ ] All files created in correct directories
- [ ] Product ID created in App Store Connect
- [ ] Product ID created in Google Play Console
- [ ] DatabaseHelper includes purchase tables
- [ ] IAPBloc initialized in main.dart
- [ ] IAPManager initializes without errors
- [ ] Product fetches successfully
- [ ] Purchase flow initiates (native UI appears)
- [ ] Pro status updates after purchase
- [ ] Pro status persists after app restart
- [ ] Restore purchases works on fresh install
- [ ] Error handling shows appropriate messages
- [ ] SnackBar notifications appear for success/error
- [ ] Both light and dark themes display correctly
- [ ] Transaction dates parsed correctly (debug logs)
- [ ] Currency code cached from store
- [ ] Purchase stream handles canceled purchases
- [ ] No crashes on simulator (iOS)
- [ ] Works on real devices (iOS & Android)

---

## Summary

This complete IAP module includes:

✅ **Singleton IAPManager** - Handles all store operations  
✅ **BLoC Pattern** - State management with 6 events/5 states  
✅ **Models** - IAPProduct, PurchaseModel, ProStatus  
✅ **Database** - SQLite persistence with upgrade path  
✅ **UI Components** - Example widgets + styling  
✅ **Error Handling** - Platform-specific debugging  
✅ **Cross-Platform** - iOS & Android support  
✅ **Security** - Store as source of truth  
✅ **Background Updates** - ValueNotifiers for real-time sync  

Copy all these files to your project and update imports to match your package name. The system is production-ready!


